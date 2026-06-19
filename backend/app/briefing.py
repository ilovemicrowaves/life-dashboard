"""Dunne AI-briefing per afspraak.

Het zaadje, niet het volledige systeem: pak de afspraak + een naïef-gematchte
set recente logs, en vraag OpenRouter om een kort, feitelijk, vooruitkijkend
paragraafje. Bewust geen oordelen of scores.
"""

from __future__ import annotations

import re
import sqlite3

from . import db
from .clock import now_local
from .config import Settings
from .llm import LLMClient

# Een kleine NL-stopwoordenlijst — genoeg voor naïeve matching.
_STOP = {
    "de", "het", "een", "en", "van", "te", "in", "op", "met", "voor", "aan", "om",
    "dat", "die", "deze", "naar", "bij", "als", "ook", "maar", "niet", "wel",
    "ik", "je", "we", "ze", "er", "is", "was", "zijn", "heb", "had", "wil",
    "even", "nog", "dan", "wat", "hoe", "over", "door", "uit", "tot", "per",
}


def _keywords(*texts: str) -> set[str]:
    blob = " ".join(t for t in texts if t).lower()
    words = re.findall(r"[a-zà-ÿ0-9]{4,}", blob)
    return {w for w in words if w not in _STOP}


def find_related_logs(conn: sqlite3.Connection, summary: str, description: str | None, limit: int = 5) -> list[dict]:
    kws = _keywords(summary, description or "")
    with db.lock():
        rows = conn.execute(
            "SELECT date, text, theme FROM logs ORDER BY date DESC, position ASC LIMIT 60"
        ).fetchall()

    scored: list[tuple[int, int, dict]] = []
    for idx, r in enumerate(rows):
        text = r["text"].lower()
        score = sum(1 for k in kws if k in text)
        if score:
            scored.append((score, -idx, dict(r)))  # -idx: bij gelijke score recenter eerst
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [item[2] for item in scored[:limit]]


def _render_user(event: dict, related: list[dict]) -> str:
    parts = [f"Afspraak: {event['summary']}"]
    when = "Hele dag" if event["all_day"] else event["start_local"].replace("T", " ")
    parts.append(f"Wanneer: {when}")
    if event.get("location"):
        parts.append(f"Locatie: {event['location']}")
    if event.get("description"):
        parts.append(f"Omschrijving: {event['description']}")
    if related:
        parts.append("\nMogelijk relevante recente logs:")
        for r in related:
            parts.append(f"- ({r['date']}) {r['text']}")
    else:
        parts.append("\n(Geen duidelijk gerelateerde logs gevonden.)")
    return "\n".join(parts)


_SYSTEM = (
    "Je schrijft een hele korte, feitelijke briefing voor één agenda-afspraak. "
    "Schrijf in het Nederlands, maximaal drie zinnen, vooruitkijkend en neutraal. "
    "Gebruik de meegegeven logs alleen als ze echt relevant zijn. "
    "Geef GEEN oordeel, GEEN cijfer of score, en stel GEEN waarom-vragen. "
    "Geen aannames verzinnen die niet uit de gegevens volgen."
)


async def build_briefing(
    conn: sqlite3.Connection,
    settings: Settings,
    llm: LLMClient,
    event: dict,
    *,
    refresh: bool = False,
) -> dict:
    eid = event["id"]
    if not refresh:
        with db.lock():
            cached = conn.execute(
                "SELECT text FROM briefings WHERE event_id = ?", (eid,)
            ).fetchone()
        if cached:
            return {"event_id": eid, "text": cached["text"], "cached": True, "configured": True}

    related = find_related_logs(conn, event["summary"], event.get("description"))
    text = await llm.generate(_SYSTEM, _render_user(event, related))

    if text is None:
        return {
            "event_id": eid,
            "text": "AI-briefing is niet geconfigureerd. Zet OPENROUTER_API_KEY om "
            "korte briefings per afspraak te krijgen.",
            "cached": False,
            "configured": False,
        }

    with db.lock():
        conn.execute(
            "INSERT INTO briefings(event_id, text, created_at) VALUES(?,?,?) "
            "ON CONFLICT(event_id) DO UPDATE SET text=excluded.text, created_at=excluded.created_at",
            (eid, text, now_local(settings.dashboard_tz).isoformat(timespec="seconds")),
        )
        conn.commit()

    return {"event_id": eid, "text": text, "cached": False, "configured": True}
