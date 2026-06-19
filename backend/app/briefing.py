"""AI-briefing per afspraak — slimme matching + context.

Fases in de matching:
  1. Gelaagde keyword-extractie (eigennamen, frases, losse woorden, samenstellingen)
  2. Tweeweg-matching (event→log én log→event)
  3. Datum-proximity (vandaag > gisteren > deze week)
  4. Thema-context (werk/gezondheid/sociaal/creatief/sport uit titel+tijd)
  5. Score-samenvoeging → top 5 gematcht + 3 recente logs
  6. Fallback: 0 matches → 5 meest recente logs
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timedelta

from . import db
from .clock import now_local, today_local
from .config import Settings
from .llm import LLMClient

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# NL-stopwoorden (uitgebreider dan eerst).
_STOP: set[str] = {
    "de", "het", "een", "en", "van", "te", "in", "op", "met", "voor", "aan",
    "om", "dat", "die", "deze", "naar", "bij", "als", "ook", "maar", "niet",
    "wel", "ik", "je", "we", "ze", "er", "is", "was", "zijn", "heb", "had",
    "wil", "zou", "kan", "moet", "nog", "dan", "wat", "hoe", "over", "door",
    "uit", "tot", "per", "zich", "hem", "haar", "mijn", "jouw", "ons", "jullie",
    "doen", "doet", "deed", "ga", "gaat", "ging", "kom", "komt", "kwam",
    "toen", "nu", "straks", "altijd", "nooit", "soms", "vaak", "weer",
    "al", "heel", "erg", "veel", "weinig", "meer", "minder", "hier", "daar",
    "waar", "worden", "wordt", "werd", "hebben", "heeft", "this", "that",
    "and", "for", "the", "with", "from", "are", "you", "your", "our",
}

# Woorden die te algemeen zijn om als keyword te dienen.
_TOO_COMMON: set[str] = {
    "afspraak", "agenda", "vandaag", "morgen", "overmorgen", "week",
    "maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag",
    "zondag", "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december",
}

_IGNORE = _STOP | _TOO_COMMON


# ---------------------------------------------------------------------------
# Fase 1 — Gelaagde keyword-extractie
# ---------------------------------------------------------------------------

def _extract_keywords(text: str) -> dict[str, list[tuple[str, int]]]:
    """Extraheer keywords uit een tekst in vier lagen.

    Returns:
      {"A": [(kw, weight), ...], "B": [...], "C": [...], "D": [...]}
      Gewichten: A=3, B=2, C=1, D=1
    """
    if not text:
        return {"A": [], "B": [], "C": [], "D": []}

    # Type A — Eigennamen / projectnamen: opeenvolgende hoofdletter-woorden.
    proper: list[tuple[str, int]] = []
    proper_pattern = re.compile(r"\b(?:[A-Z][a-zà-ÿ]{1,}(?:[ \t]+[A-Z][a-zà-ÿ]{1,})*)\b")
    seen_a: set[str] = set()
    for m in proper_pattern.finditer(text):
        kw = m.group(0).strip()
        low = kw.lower()
        if low not in _IGNORE and len(kw) >= 2 and low not in seen_a:
            proper.append((low, 3))
            seen_a.add(low)

    # Type B — Bigrams en trigrams van niet-stopwoorden.
    phrases: list[tuple[str, int]] = []
    words = [w.lower() for w in re.findall(r"[a-zà-ÿ0-9]{2,}", text.lower())]
    clean = [w for w in words if w not in _IGNORE and len(w) >= 2]
    seen_b: set[str] = set()
    for n in (2, 3):
        for i in range(len(clean) - n + 1):
            kw = " ".join(clean[i : i + n])
            if kw not in seen_b and len(kw) >= 6:  # minimale frase-lengte
                phrases.append((kw, 2))
                seen_b.add(kw)

    # Type C — Losse trefwoorden ≥3 karakters, minus stopwoorden.
    singles: list[tuple[str, int]] = []
    seen_c: set[str] = set()
    for w in words:
        if len(w) >= 3 and w not in _IGNORE and w not in seen_c and w not in seen_a:
            singles.append((w, 1))
            seen_c.add(w)

    # Type D — Samenstellingen ≥8 karakters: split in substrings van 5+ chars.
    compounds: list[tuple[str, int]] = []
    long_words = [w for w in words if len(w) >= 8 and w not in seen_a]
    seen_d: set[str] = set()
    for w in long_words:
        # Schuif een venster van 5+ karakters over het woord.
        for i in range(len(w) - 4):
            for j in range(i + 5, len(w) + 1):
                sub = w[i:j]
                if sub not in seen_d and sub not in _IGNORE and sub != w:
                    compounds.append((sub, 1))
                    seen_d.add(sub)
        # Max 6 substrings per lang woord (explosie tegengaan).
        if len(compounds) > 6 * len(long_words):
            compounds = compounds[:6 * len(long_words)]

    return {"A": proper, "B": phrases, "C": singles, "D": compounds}


def _all_keywords(keywords: dict) -> list[tuple[str, int]]:
    """Alle keywords uit de vier lagen als platte lijst van (kw, weight)."""
    return [item for k in ("A", "B", "C", "D") for item in keywords.get(k, [])]


# ---------------------------------------------------------------------------
# Fase 2 — Tweeweg-matching
# ---------------------------------------------------------------------------

def _score_log(log_text: str, event_kws: dict) -> float:
    """Score één log-tekst tegen de event-keywords (event→log).

    Ook log→event: keywords uit de log matchen tegen het event.
    Die secundaire richting krijgt factor 0.5.
    """
    text_lower = log_text.lower()
    score: float = 0.0

    # Event → log.
    all_kws = _all_keywords(event_kws)
    for kw, weight in all_kws:
        if kw in text_lower:
            score += weight

    # Log → event (secundair, 0.5×).
    log_kws = _extract_keywords(log_text)
    log_type_c = [kw for kw, _ in log_kws["C"]]
    # Verzamel alle event-tekst om tegen te matchen.
    event_text = " ".join(kw for kw, _ in all_kws).lower()
    for kw in log_type_c:
        if kw in event_text:
            score += 0.5

    return score


# ---------------------------------------------------------------------------
# Fase 3 — Datum-proximity
# ---------------------------------------------------------------------------

def _date_proximity(log_date_str: str, event_date_str: str) -> int:
    """Score op basis van hoe dicht de log bij het event ligt.

    Zelfde dag: +3, 1 dag: +2, zelfde week: +1, ouder: 0.
    """
    try:
        log_d = date.fromisoformat(log_date_str)
        event_d = date.fromisoformat(event_date_str)
    except (ValueError, TypeError):
        return 0
    diff = abs((event_d - log_d).days)
    if diff == 0:
        return 3
    elif diff == 1:
        return 2
    elif diff <= 7:
        return 1
    return 0


# ---------------------------------------------------------------------------
# Fase 4 — Thema-context
# ---------------------------------------------------------------------------

# Detection-regels voor event-context.
_CONTEXT_RULES: list[tuple[str, set[str], set[str]]] = [
    # (context-naam, titel-keywords, thema's om bonus op te geven)
    ("werk", {
        "overleg", "meeting", "bespreking", "project", "deadline",
        "presentatie", "demo", "review", "standup", "sprint", "planning",
        "team", "klant", "klantgesprek", "offerte", "factuur", "rapportage",
        "briefing", "functioneringsgesprek", "beoordeling", "salaris",
        "sollicitatie", "interview", "workshop", "training", "cursus",
        "congres", "conferentie", "college", "tentamen", "examen",
    }, {"werk"}),
    ("gezondheid", {
        "arts", "dokter", "tandarts", "ziekenhuis", "apotheek", "fysio",
        "therapeut", "psycholoog", "psychiater", "bloed", "afspraak",
        "consult", "specialist", "huisarts", "chirurg", "behandeling",
        "operatie", "controle", "vaccinatie", "griepprik",
    }, {"gezondheid"}),
    ("sociaal", {
        "koffie", "lunch", "eten", "diner", "drinken", "borrel", "feest",
        "verjaardag", "barbecue", "picknick", "uitje", "afspreken",
        "bijpraten", "ontbijt", "brunch", "high tea", "wijnproeverij",
        "spelletjesavond", "filmavond",
    }, {"relatie", "sociaal"}),
    ("creatief", {
        "brainstorm", "bedenken", "verzinnen", "ontwerpen", "schetsen",
        "idee", "concept", "creatief", "schrijven", "tekenen", "schilderen",
        "muziek", "componeren", "fotograferen", "filmen",
    }, {"idee"}),
    ("sport", {
        "sport", "trainen", "hardlopen", "fietsen", "zwemmen", "gym",
        "yoga", "wedstrijd", "competitie", "toernooi", "klimmen",
        "boulderen", "voetbal", "tennis", "hockey", "basketbal",
        "volleybal", "fitness", "crossfit", "pilates", "wandelen",
        "hiken", "surfen", "skateboarden", "schaatsen", "ski",
    }, {"gezondheid", "sport"}),
]


def _detect_context(summary: str, start_local: str, all_day: bool) -> str | None:
    """Bepaal de context van een event uit titel + tijd."""
    title_lower = summary.lower()
    for context, keywords, _ in _CONTEXT_RULES:
        if any(kw in title_lower for kw in keywords):
            return context

    # Als geen keyword matcht: check of het een werkdag + kantooruren is.
    if not all_day and start_local:
        try:
            dt = datetime.fromisoformat(start_local)
            if dt.weekday() < 5 and 7 <= dt.hour <= 19:
                return "werk"
        except (ValueError, TypeError):
            pass

    return None


def _theme_bonus(context: str | None, log_theme: str) -> int:
    """Score op basis van match tussen event-context en log-thema."""
    if context is None or not log_theme:
        return 0
    # Generieke logs zijn altijd een zwak signaal.
    if log_theme == "algemeen":
        return 1
    # Zoek of deze context dit thema waardeert.
    for ctx_name, _, themes in _CONTEXT_RULES:
        if ctx_name == context:
            return 2 if log_theme in themes else 0
    return 0


# ---------------------------------------------------------------------------
# Fase 5 & 6 — Samenvoeging & selectie
# ---------------------------------------------------------------------------

def find_related_logs(
    conn: sqlite3.Connection,
    event: dict,
    settings: Settings,
) -> tuple[list[dict], list[dict]]:
    """Geeft (gematchte_logs, recente_logs) voor één event.

    Gematchte logs: top 5 op score (score > 0).
    Recente logs: laatste 3, altijd (state-of-mind), geen dubbelingen.
    """
    summary = event.get("summary", "") or ""
    description = event.get("description") or ""
    start_local = event.get("start_local", "") or ""
    all_day = bool(event.get("all_day", False))
    event_date_str = event.get("start_date", "") or today_local(settings.dashboard_tz).isoformat()

    # Fase 1 — keywords uit de afspraak.
    event_kws = _extract_keywords(f"{summary}\n{description}")

    # Fase 4 — context-detectie.
    context = _detect_context(summary, start_local, all_day)

    # Lees alle recente logs (max 60, genoeg voor een persoonlijke vault).
    with db.lock():
        rows = conn.execute(
            "SELECT date, text, theme FROM logs ORDER BY date DESC, position ASC LIMIT 60"
        ).fetchall()

    scored: list[tuple[float, int, dict]] = []
    for idx, r in enumerate(rows):
        log_text = r["text"] or ""
        log_date = r["date"] or ""
        log_theme = r["theme"] or ""

        # Fase 2 — twee-weg keyword-score.
        kw_score = _score_log(log_text, event_kws)

        # Fase 3 — datum-proximity.
        date_score = _date_proximity(log_date, event_date_str)

        # Fase 4 — thema-bonus.
        theme_score = _theme_bonus(context, log_theme)

        total = kw_score + date_score + theme_score

        # Alle vandaag-logs zijn minimaal 1 (state-of-mind).
        if total <= 0 and _date_proximity(log_date, event_date_str) == 3:
            total = 1.0

        if total > 0:
            scored.append((total, -idx, dict(r)))

    # Sorteer: hoogste score eerst, bij gelijke score nieuwste eerst (-idx).
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    # Top 5 gematchte logs.
    matched = [item[2] for item in scored[:5]]

    # Recente logs: laatste 3 die niet al in matched zitten.
    matched_texts = {m["text"] for m in matched}
    recent: list[dict] = []
    for r in rows[:15]:  # kijk alleen in de echte recente logs
        if len(recent) >= 3:
            break
        if r["text"] not in matched_texts:
            recent.append(dict(r))
            matched_texts.add(r["text"])

    return matched, recent


# ---------------------------------------------------------------------------
# Prompt-rendering
# ---------------------------------------------------------------------------

def _get_todays_other_events(
    conn: sqlite3.Connection, event_id: str, today_iso: str
) -> list[dict]:
    """Andere afspraken vandaag (exclusief het event zelf)."""
    with db.lock():
        rows = conn.execute(
            "SELECT summary, start_local, all_day, location FROM events "
            "WHERE start_date = ? AND id != ? "
            "ORDER BY all_day DESC, start_local ASC",
            (today_iso, event_id),
        ).fetchall()
    out: list[dict] = []
    for r in rows:
        if r["all_day"]:
            label = "Hele dag"
        else:
            label = (r["start_local"] or "")[11:16]
        out.append({"summary": r["summary"], "time": label, "location": r["location"]})
    return out


def _render_user(
    event: dict,
    matched: list[dict],
    recent: list[dict],
    other_events: list[dict],
    settings: Settings,
) -> str:
    """Bouw een gestructureerd user-bericht voor de LLM."""
    parts: list[str] = []

    # --- De afspraak zelf ---
    parts.append("AFSPRAAK")
    parts.append(f"Titel: {event['summary']}")
    if event.get("all_day"):
        parts.append("Tijd: Hele dag")
    else:
        when = (event.get("start_local") or "").replace("T", " ")
        parts.append(f"Tijd: {when}")
    if event.get("location"):
        parts.append(f"Locatie: {event['location']}")
    if event.get("description"):
        parts.append(f"Omschrijving: {event['description']}")
    parts.append("")

    # --- Andere afspraken vandaag ---
    parts.append("VANDAAG (andere afspraken)")
    if other_events:
        for oe in other_events:
            loc = f" ({oe['location']})" if oe.get("location") else ""
            parts.append(f"  {oe['time']}  {oe['summary']}{loc}")
    else:
        parts.append("  (Geen andere afspraken.)")
    parts.append("")

    # --- Gematchte logs ---
    parts.append("JOELS LOGS (mogelijk relevant)")
    if matched:
        for r in matched:
            parts.append(f"  [{r['date']}] {r['text']}  #log/{r.get('theme','algemeen')}")
    else:
        parts.append("  (Geen logs gevonden die duidelijk met deze afspraak te maken hebben.)")
    parts.append("")

    # --- Recente logs (state of mind) ---
    if recent:
        parts.append("RECENTE LOGS (Joels state of mind)")
        for r in recent:
            parts.append(f"  [{r['date']}] {r['text']}  #log/{r.get('theme','algemeen')}")
        parts.append("")

    # --- Tijdsbesef ---
    now = now_local(settings.dashboard_tz)
    parts.append(f"Huidige datum/tijd: {now.strftime('%A %-d %B %Y, %H:%M')}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM = (
    "Je bent een persoonlijke assistent van Joel. Je schrijft een korte briefing "
    "bij één agenda-afspraak.\n\n"
    "Je krijgt vier blokken informatie:\n"
    "1. AFSPRAAK — de afspraak zelf\n"
    "2. VANDAAG — andere afspraken vandaag (voor context over drukte/planning)\n"
    "3. JOELS LOGS — logs die mogelijk relevant zijn\n"
    "4. RECENTE LOGS — Joels meest recente logs (zijn 'state of mind')\n\n"
    "SCHRIJF één paragraaf van 2 tot 4 zinnen in het Nederlands.\n\n"
    "Structuur:\n"
    "- Begin met wat er op de planning staat: feitelijk, niet de titel herhalen, "
    "maar wat betekent dit concreet? Bijv. 'Je hebt een overleg met Mark om 10:00 "
    "bij Coffee Company' in plaats van 'Afspraak: Koffie met Mark'.\n"
    "- Als er een relevante log is: benoem kort het verband. "
    "Bijv. 'Je hebt vanochtend aan project Alpha gewerkt — dat sluit aan.'\n"
    "- Als er géén duidelijke match is: gebruik RECENTE LOGS voor subtiele context. "
    "Bijv. 'Je had veel energie vandaag — mooi moment voor dit gesprek.' "
    "of 'Je gaf aan slecht geslapen te hebben, houd daar rekening mee.'\n"
    "- Sluit eventueel af met iets om rekening mee te houden: tijd, overlap met "
    "een andere afspraak, voorbereiding. Maar alleen als er echt iets te zeggen valt.\n\n"
    "TOON: neutraal, informatief, alsof een goede vriend het zegt. "
    "Spreek Joel aan met 'je'. Nederlands (niet Vlaams, niet formeel).\n\n"
    "NOOIT:\n"
    "- Oordelen of scores geven ('goed gedaan', 'dat is slecht')\n"
    "- 'Waarom'-vragen stellen\n"
    "- Dingen verzinnen die niet in de aangeleverde gegevens staan\n"
    "- De titel van de afspraak letterlijk herhalen als eerste zin\n"
    "- Zeggen 'De logs geven aan dat...' of meta-taal over de logs gebruiken — "
    "verwerk de info natuurlijk"
)


# ---------------------------------------------------------------------------
# Cache — TTL + invalidatie
# ---------------------------------------------------------------------------

_CACHE_TTL_HOURS = 1


def invalidate_briefing_cache_for_today(conn: sqlite3.Connection, settings: Settings) -> None:
    """Verwijder alle briefings van vandaag (zodat ze opnieuw gegenereerd worden
    met de nieuwste logs). Wordt aangeroepen na elke log-append."""
    today = today_local(settings.dashboard_tz).isoformat()
    with db.lock():
        conn.execute(
            "DELETE FROM briefings WHERE event_id IN "
            "(SELECT id FROM events WHERE start_date = ?)",
            (today,),
        )
        conn.commit()


async def build_briefing(
    conn: sqlite3.Connection,
    settings: Settings,
    llm: LLMClient,
    event: dict,
    *,
    refresh: bool = False,
) -> dict:
    eid = event["id"]
    now = now_local(settings.dashboard_tz)

    # Cache-check met TTL.
    if not refresh:
        with db.lock():
            cached = conn.execute(
                "SELECT text, created_at FROM briefings WHERE event_id = ?", (eid,)
            ).fetchone()
        if cached:
            try:
                created = datetime.fromisoformat(cached["created_at"])
                if (now - created) < timedelta(hours=_CACHE_TTL_HOURS):
                    return {
                        "event_id": eid,
                        "text": cached["text"],
                        "cached": True,
                        "configured": True,
                    }
            except (ValueError, TypeError):
                pass  # TTL-check gefaald → opnieuw genereren.

    # Bouw de rijke context op.
    matched, recent = find_related_logs(conn, event, settings)
    today_iso = event.get("start_date", "") or now.strftime("%Y-%m-%d")
    other_events = _get_todays_other_events(conn, eid, today_iso)
    user_prompt = _render_user(event, matched, recent, other_events, settings)

    text = await llm.generate(_SYSTEM, user_prompt)

    if text is None:
        return {
            "event_id": eid,
            "text": (
                "AI-briefing is niet geconfigureerd. Zet OPENROUTER_API_KEY om "
                "korte briefings per afspraak te krijgen."
            ),
            "cached": False,
            "configured": False,
        }

    # Cache wegschrijven met huidige tijd.
    created_str = now.isoformat(timespec="seconds")
    with db.lock():
        conn.execute(
            "INSERT INTO briefings(event_id, text, created_at) VALUES(?,?,?) "
            "ON CONFLICT(event_id) DO UPDATE SET text=excluded.text, "
            "created_at=excluded.created_at",
            (eid, text, created_str),
        )
        conn.commit()

    return {"event_id": eid, "text": text, "cached": False, "configured": True}
