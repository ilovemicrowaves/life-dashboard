"""Google Calendar API — events aanmaken (tweeweg-sync).

Flow:
  Refresh token (uit OAuth2 Playground, in .env) → access token (gecached in
  SQLite meta) → Google Calendar API v3.

De refresh token is long-lived; de access token verloopt na ~1 uur.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import httpx

from . import db
from .config import Settings

TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


def get_valid_token(settings: Settings) -> str:
    """Geeft een geldig access token (uit cache of via refresh)."""
    conn = db.get_conn(settings.index_db)
    now = datetime.now(timezone.utc)

    # Check cache.
    cached = db.get_meta(conn, "google_access_token")
    expiry_str = db.get_meta(conn, "google_token_expiry")
    if cached and expiry_str:
        try:
            expiry = datetime.fromisoformat(expiry_str)
            if now < expiry - timedelta(minutes=2):  # marge van 2 min
                return cached
        except (ValueError, TypeError):
            pass  # Ongeldige expiry → opnieuw aanvragen.

    # Refresh.
    resp = httpx.post(
        TOKEN_URL,
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": settings.google_refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    data = resp.json()

    access_token = data["access_token"]
    expires_in = data.get("expires_in", 3600)
    expires_at = now + timedelta(seconds=expires_in)

    db.set_meta(conn, "google_access_token", access_token)
    db.set_meta(conn, "google_token_expiry", expires_at.isoformat())

    return access_token


def create_event(
    settings: Settings,
    summary: str,
    start: str,
    end: str,
    *,
    description: str | None = None,
    location: str | None = None,
    all_day: bool = False,
) -> dict:
    """Maak een event aan in de primaire Google Calendar.

    Args:
        summary: titel van de afspraak
        start: ISO 8601 datetime (2026-06-20T10:00:00) of date (2026-06-20)
        end: ISO 8601 datetime of date
        description: optionele omschrijving
        location: optionele locatie
        all_day: hele-dag-event (start/end zijn dan dates, geen datetimes)
    """
    token = get_valid_token(settings)

    body: dict = {
        "summary": summary.strip(),
    }

    if all_day:
        body["start"] = {"date": start}
        body["end"] = {"date": end}
    else:
        tz = settings.dashboard_tz
        body["start"] = {"dateTime": start, "timeZone": tz}
        body["end"] = {"dateTime": end, "timeZone": tz}

    if description and description.strip():
        body["description"] = description.strip()
    if location and location.strip():
        body["location"] = location.strip()

    resp = httpx.post(
        CALENDAR_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=15.0,
    )

    if resp.status_code == 401:
        # Token verlopen ondanks cache → purgeer cache en retry één keer.
        conn = db.get_conn(settings.index_db)
        db.set_meta(conn, "google_access_token", "")
        token = get_valid_token(settings)
        resp = httpx.post(
            CALENDAR_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=15.0,
        )

    resp.raise_for_status()
    return resp.json()
