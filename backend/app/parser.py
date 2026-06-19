"""Ingest: markdown -> logs, ICS -> events. En de volledige rebuild.

De parser is bewust mild. Verandert de log-conventie later, dan pas je hier iets
aan en draai je rebuild — de notities en de app blijven heel.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import recurring_ical_events
from icalendar import Calendar

from . import db
from .clock import today_local
from .config import Settings

# Een regel is een log als hij een #log/<thema>-tag bevat. De tekst is de regel
# zonder bullet en zonder de tag. Tag-plaatsing maakt niet uit (mild).
LOG_TAG_RE = re.compile(r"#log/([A-Za-z0-9_][A-Za-z0-9_\-/]*)")
BULLET_RE = re.compile(r"^[\s>]*[-*+]\s+")
FILENAME_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


# --------------------------------------------------------------------------
# Markdown -> logs
# --------------------------------------------------------------------------

def parse_log_lines(text: str) -> list[tuple[str, str, int, str]]:
    """Geef (tekst, thema, positie, raw) per logregel. positie 0 = bovenaan."""
    rows: list[tuple[str, str, int, str]] = []
    lines = text.splitlines()
    i = 0
    n = len(lines)

    # Frontmatter aan het begin overslaan.
    if n and lines[0].strip() == "---":
        j = 1
        while j < n and lines[j].strip() != "---":
            j += 1
        i = j + 1 if j < n else n

    pos = 0
    while i < n:
        line = lines[i]
        i += 1
        m = LOG_TAG_RE.search(line)
        if not m:
            continue
        theme = m.group(1)
        body = BULLET_RE.sub("", line)
        body = LOG_TAG_RE.sub("", body)
        body = re.sub(r"\s+", " ", body).strip()
        if not body:
            continue
        rows.append((body, theme, pos, line.rstrip()))
        pos += 1
    return rows


def file_date(path: Path) -> str:
    """Datum van een notitie: uit de bestandsnaam (YYYY-MM-DD), anders mtime."""
    m = FILENAME_DATE_RE.search(path.stem)
    if m:
        return m.group(1)
    return date.fromtimestamp(path.stat().st_mtime).isoformat()


def iter_markdown_files(vault_path: Path):
    if not vault_path.exists():
        return
    for p in sorted(vault_path.rglob("*.md")):
        # Sla verborgen mappen over (.obsidian, .trash, .git, ...).
        if any(part.startswith(".") for part in p.relative_to(vault_path).parts):
            continue
        yield p


def reindex_file(conn: sqlite3.Connection, vault_path: Path, path: Path) -> int:
    """(Her)indexeer de logs van één markdown-bestand. Geeft aantal logs terug."""
    rel = str(path.relative_to(vault_path)) if path.is_relative_to(vault_path) else str(path)
    d = file_date(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        text = ""
    rows = parse_log_lines(text)
    with db.lock():
        conn.execute("DELETE FROM logs WHERE source_file = ?", (rel,))
        conn.executemany(
            "INSERT INTO logs(date, text, theme, source_file, position, raw) "
            "VALUES(?,?,?,?,?,?)",
            [(d, body, theme, rel, pos, raw) for (body, theme, pos, raw) in rows],
        )
        conn.commit()
    return len(rows)


def collect_logs(conn: sqlite3.Connection, settings: Settings) -> int:
    total = 0
    for path in iter_markdown_files(settings.vault_path):
        total += reindex_file(conn, settings.vault_path, path)
    return total


# --------------------------------------------------------------------------
# ICS -> events
# --------------------------------------------------------------------------

def _ics_sources(settings: Settings) -> list[tuple[bytes, str]]:
    """Lees alle ICS-bronnen: eerst bestand(en) in de vault, dan de URL."""
    sources: list[tuple[bytes, str]] = []

    ics_file = settings.ics_file.strip()
    if ics_file:
        p = Path(ics_file)
        if p.is_dir():
            for f in sorted(p.glob("*.ics")):
                sources.append((f.read_bytes(), f"file:{f.name}"))
        elif p.is_file():
            sources.append((p.read_bytes(), f"file:{p.name}"))

    url = settings.ics_url.strip()
    if url:
        try:
            r = httpx.get(url, timeout=15.0, follow_redirects=True)
            r.raise_for_status()
            sources.append((r.content, "url"))
        except Exception as exc:  # ICS-URL down mag de rest niet breken
            print(f"[ics] kon URL niet ophalen: {exc}")

    return sources


def _to_local(value, tz: ZoneInfo):
    """Normaliseer DTSTART/DTEND naar (start_utc|None, start_local, start_date, all_day)."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=tz)  # floating -> lokaal
        local = value.astimezone(tz)
        utc_iso = value.astimezone(ZoneInfo("UTC")).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"
        return utc_iso, local.replace(tzinfo=None).isoformat(timespec="seconds"), local.date().isoformat(), False
    # date -> hele dag
    return None, value.isoformat(), value.isoformat(), True


def expand_events(raw: bytes, source: str, tz: ZoneInfo, start, end) -> list[dict]:
    cal = Calendar.from_ical(raw)
    out: list[dict] = []
    for ev in recurring_ical_events.of(cal).between(start, end):
        dtstart = ev.get("DTSTART")
        if dtstart is None:
            continue
        start_utc, start_local, start_date, all_day = _to_local(dtstart.dt, tz)

        end_utc = end_local = None
        dtend = ev.get("DTEND")
        if dtend is not None:
            end_utc, end_local, _, _ = _to_local(dtend.dt, tz)

        uid = str(ev.get("UID", "")) or ""
        summary = str(ev.get("SUMMARY", "")).strip() or "(geen titel)"
        description = str(ev.get("DESCRIPTION", "")).strip() or None
        location = str(ev.get("LOCATION", "")).strip() or None

        eid = hashlib.sha1(f"{uid}|{start_local}".encode("utf-8")).hexdigest()[:16]
        out.append(
            {
                "id": eid,
                "uid": uid,
                "summary": summary,
                "description": description,
                "location": location,
                "start_utc": start_utc,
                "end_utc": end_utc,
                "start_local": start_local,
                "end_local": end_local,
                "start_date": start_date,
                "all_day": 1 if all_day else 0,
                "source": source,
            }
        )
    return out


def collect_events(conn: sqlite3.Connection, settings: Settings) -> int:
    tz = ZoneInfo(settings.dashboard_tz)
    today = today_local(settings.dashboard_tz)
    # Royaal venster zodat 'vandaag + deze week' altijd gedekt is, ook een paar
    # dagen na een rebuild. Verder vooruit dan deze week tonen we (nog) niet.
    window_start = datetime.combine(today - timedelta(days=7), datetime.min.time(), tz)
    window_end = datetime.combine(today + timedelta(days=31), datetime.min.time(), tz)

    rows: list[dict] = []
    for raw, source in _ics_sources(settings):
        try:
            rows.extend(expand_events(raw, source, tz, window_start, window_end))
        except Exception as exc:
            print(f"[ics] kon bron {source} niet parsen: {exc}")

    with db.lock():
        for r in rows:
            conn.execute(
                "INSERT OR REPLACE INTO events"
                "(id, uid, summary, description, location, start_utc, end_utc,"
                " start_local, end_local, start_date, all_day, source)"
                " VALUES(:id,:uid,:summary,:description,:location,:start_utc,:end_utc,"
                ":start_local,:end_local,:start_date,:all_day,:source)",
                r,
            )
        conn.commit()
    return len(rows)


# --------------------------------------------------------------------------
# Volledige rebuild
# --------------------------------------------------------------------------

def rebuild(conn: sqlite3.Connection, settings: Settings) -> dict:
    """Gooi de index weg en bouw 'm volledig opnieuw op uit de bron."""
    from .clock import now_local

    with db.lock():
        db.drop_all(conn)
        n_logs = collect_logs(conn, settings)
        n_events = collect_events(conn, settings)
        db.set_meta(conn, "last_rebuild", now_local(settings.dashboard_tz).isoformat(timespec="seconds"))
    return {"logs": n_logs, "events": n_events}
