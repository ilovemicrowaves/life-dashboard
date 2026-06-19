"""SQLite-index: een herbouwbare cache.

Principe: dit bestand mag je altijd weggooien. Alle data hierin komt uit de
markdown-vault en de ICS-bron en kan volledig opnieuw opgebouwd worden.

We houden één gedeelde connectie per db-pad en serialiseren toegang met een
lock. Voor één gebruiker op een LAN is dat ruim voldoende en simpel.
"""

import sqlite3
import threading
from pathlib import Path

_CONNS: dict[str, sqlite3.Connection] = {}
_LOCK = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,          -- YYYY-MM-DD (uit bestandsnaam, fallback mtime)
    text        TEXT NOT NULL,
    theme       TEXT NOT NULL,
    source_file TEXT NOT NULL,
    position    INTEGER NOT NULL,       -- volgorde binnen het bestand (0 = bovenaan = nieuwste)
    raw         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_logs_date ON logs(date);
CREATE INDEX IF NOT EXISTS idx_logs_source ON logs(source_file);

CREATE TABLE IF NOT EXISTS events (
    id          TEXT PRIMARY KEY,       -- stabiele hash(uid|start_local)
    uid         TEXT,
    summary     TEXT NOT NULL,
    description TEXT,
    location    TEXT,
    start_utc   TEXT,                   -- ISO UTC (null bij hele dag)
    end_utc     TEXT,
    start_local TEXT NOT NULL,          -- ISO lokaal (naive)
    end_local   TEXT,
    start_date  TEXT NOT NULL,          -- YYYY-MM-DD lokaal (voor filteren)
    all_day     INTEGER NOT NULL DEFAULT 0,
    source      TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(start_date);

CREATE TABLE IF NOT EXISTS briefings (
    event_id   TEXT PRIMARY KEY,
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

_TABLES = ["logs", "events", "briefings", "meta"]


def get_conn(index_db: Path) -> sqlite3.Connection:
    key = str(Path(index_db).resolve())
    with _LOCK:
        conn = _CONNS.get(key)
        if conn is None:
            Path(index_db).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(index_db, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            _CONNS[key] = conn
        return conn


def init_schema(conn: sqlite3.Connection) -> None:
    with _LOCK:
        conn.executescript(SCHEMA)
        conn.commit()


def drop_all(conn: sqlite3.Connection) -> None:
    """Gooi de hele index weg (alle tabellen) en herbouw het lege schema."""
    with _LOCK:
        for table in _TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
        conn.executescript(SCHEMA)
        conn.commit()


def is_empty(conn: sqlite3.Connection) -> bool:
    with _LOCK:
        logs = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
        events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    return logs == 0 and events == 0


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    with _LOCK:
        conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()


def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    with _LOCK:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def close_all() -> None:
    """Sluit alle connecties (zodat het db-bestand verwijderd kan worden)."""
    with _LOCK:
        for conn in _CONNS.values():
            try:
                conn.close()
            except Exception:
                pass
        _CONNS.clear()


def lock() -> threading.RLock:
    return _LOCK
