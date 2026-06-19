"""CLI: gooi het indexbestand fysiek weg en bouw volledig opnieuw op.

    python -m app.reindex

Bewijst dat de cache wegwerpbaar is. Later kan dit ook vanuit een scheduler/cron
draaien (Fase 2+) — nu is het handmatig en via POST /api/index/rebuild.
"""

from __future__ import annotations

from pathlib import Path

from . import db, parser
from .config import get_settings


def main() -> None:
    settings = get_settings()
    db.close_all()

    p = Path(settings.index_db)
    for suffix in ("", "-wal", "-shm"):
        f = Path(str(p) + suffix)
        if f.exists():
            f.unlink()
            print(f"[reindex] verwijderd: {f}")

    conn = db.get_conn(settings.index_db)
    db.init_schema(conn)
    counts = parser.rebuild(conn, settings)
    print(f"[reindex] herbouwd uit {settings.vault_path}: {counts}")


if __name__ == "__main__":
    main()
