"""Agenda-queries op de index: vandaag (prominent) + de rest van deze week.

'Deze week' = de huidige ISO-week (ma t/m zo). We tonen vandaag apart en de
overige dagen tot en met zondag compact. Geen maand/week/dag-toggle (Fase 2+).
Displaylabels rekenen we hier uit zodat de frontend dom en TV-veilig blijft.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

from . import db
from .clock import today_local
from .config import Settings

_WEEKDAYS = ["ma", "di", "wo", "do", "vr", "za", "zo"]
_MONTHS = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


def _date_label(d: date) -> str:
    return f"{_WEEKDAYS[d.weekday()]} {d.day} {_MONTHS[d.month - 1]}"


def _time_label(row: sqlite3.Row | dict) -> str:
    if row["all_day"]:
        return "Hele dag"
    # start_local = 'YYYY-MM-DDTHH:MM:SS'
    return row["start_local"][11:16]


def _serialize(row: sqlite3.Row) -> dict:
    d = date.fromisoformat(row["start_date"])
    return {
        "id": row["id"],
        "summary": row["summary"],
        "location": row["location"],
        "all_day": bool(row["all_day"]),
        "start_local": row["start_local"],
        "start_date": row["start_date"],
        "time_label": _time_label(row),
        "date_label": _date_label(d),
        "has_description": bool(row["description"]),
    }


def get_event(conn: sqlite3.Connection, event_id: str) -> dict | None:
    with db.lock():
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    return dict(row) if row else None


def get_today_and_week(conn: sqlite3.Connection, settings: Settings) -> dict:
    today = today_local(settings.dashboard_tz)
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    today_iso = today.isoformat()

    with db.lock():
        today_rows = conn.execute(
            "SELECT * FROM events WHERE start_date = ? "
            "ORDER BY all_day DESC, start_local ASC",
            (today_iso,),
        ).fetchall()
        week_rows = conn.execute(
            "SELECT * FROM events WHERE start_date > ? AND start_date <= ? "
            "ORDER BY start_date ASC, all_day DESC, start_local ASC",
            (today_iso, sunday.isoformat()),
        ).fetchall()

    today_events = [_serialize(r) for r in today_rows]

    # Rest van de week groeperen per dag.
    week_days: list[dict] = []
    by_date: dict[str, list[dict]] = {}
    for r in week_rows:
        by_date.setdefault(r["start_date"], []).append(_serialize(r))
    for iso in sorted(by_date):
        d = date.fromisoformat(iso)
        week_days.append({"date": iso, "label": _date_label(d), "events": by_date[iso]})

    return {
        "today": {"date": today_iso, "label": _date_label(today), "events": today_events},
        "week": {"until": sunday.isoformat(), "days": week_days},
        "last_rebuild": db.get_meta(conn, "last_rebuild"),
    }


def get_recent_logs(conn: sqlite3.Connection, limit: int) -> list[dict]:
    with db.lock():
        rows = conn.execute(
            "SELECT date, text, theme FROM logs "
            "ORDER BY date DESC, position ASC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
