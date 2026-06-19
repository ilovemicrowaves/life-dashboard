"""FastAPI-app: endpoints + serveren van de statische frontend.

Endpoints (onder /api):
  GET  /api/config                 - UI-config (reload-interval, thema's, ...)
  GET  /api/agenda/today           - events vandaag + de rest van deze week
  GET  /api/agenda/{event_id}/briefing  - dunne AI-briefing voor één event
  POST /api/log                    - { text, theme } -> append aan dagnotitie + index
  GET  /api/logs/recent            - laatste N logregels
  POST /api/index/rebuild          - gooi de index weg en herbouw uit de vault
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agenda, db, parser, vault
from .briefing import build_briefing
from .config import Settings, get_settings
from .llm import LLMClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    conn = db.get_conn(settings.index_db)
    db.init_schema(conn)
    if settings.auto_rebuild_on_start and db.is_empty(conn):
        counts = parser.rebuild(conn, settings)
        print(f"[startup] index opgebouwd: {counts}")

    # Start de auto-rebuild poll-loop als die aan staat.
    poll_task: asyncio.Task | None = None
    if settings.auto_rebuild_poll_seconds > 0:
        poll_task = asyncio.create_task(_auto_rebuild_loop(settings))
        print(f"[startup] auto-rebuild poll elke {settings.auto_rebuild_poll_seconds}s")

    yield

    if poll_task:
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Life Dashboard", version="0.1.0", lifespan=lifespan)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

_llm = LLMClient(_settings)


class LogIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    theme: str | None = None


async def _auto_rebuild_loop(settings: Settings) -> None:
    """Poll met vaste interval; rebuild alleen als er een verandering in de vault is."""
    while True:
        await asyncio.sleep(settings.auto_rebuild_poll_seconds)
        try:
            if parser.vault_files_changed(settings):
                # Rebuild in een thread — SQLite is blocking.
                counts = await asyncio.to_thread(parser.rebuild, _conn(), settings)
                print(f"[auto-rebuild] verandering gedetecteerd, index herbouwd: {counts}")
        except Exception as exc:
            print(f"[auto-rebuild] fout: {exc}")


def _conn():
    return db.get_conn(get_settings().index_db)


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

@app.get("/api/config")
def api_config() -> dict:
    s = get_settings()
    return {
        "reloadMs": s.reload_interval_ms,
        "themes": s.themes_list,
        "defaultTheme": s.default_theme,
        "recentLogsCount": s.recent_logs_count,
        "llmConfigured": _llm.configured,
        "logPlaceholder": "Wat merk je op? Iets om morgen te proberen?",
    }


@app.get("/api/agenda/today")
def api_agenda_today() -> dict:
    return agenda.get_today_and_week(_conn(), get_settings())


@app.get("/api/agenda/{event_id}/briefing")
async def api_agenda_briefing(event_id: str, refresh: bool = False) -> dict:
    conn = _conn()
    event = agenda.get_event(conn, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event niet gevonden")
    return await build_briefing(conn, get_settings(), _llm, event, refresh=refresh)


@app.post("/api/log")
def api_log(body: LogIn) -> dict:
    s = get_settings()
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Lege log")
    theme = (body.theme or s.default_theme).strip() or s.default_theme

    result = vault.append_log(s, text, theme)

    # Index meteen bijwerken zodat 'recente logs' direct klopt.
    conn = _conn()
    written = Path(result["path"])
    parser.reindex_file(conn, s.vault_path, written)

    return {
        "ok": True,
        "date": result["date"],
        "line": result["line"],
        "theme": result["theme"],
        "created_note": result["created"],
    }


@app.get("/api/logs/recent")
def api_logs_recent(limit: int | None = None) -> dict:
    s = get_settings()
    n = limit or s.recent_logs_count
    return {"logs": agenda.get_recent_logs(_conn(), n)}


@app.post("/api/index/rebuild")
def api_index_rebuild() -> dict:
    s = get_settings()
    counts = parser.rebuild(_conn(), s)
    return {"ok": True, "rebuilt": counts}


@app.get("/api/health")
def api_health() -> dict:
    return {"ok": True}


# --------------------------------------------------------------------------
# Statische frontend (gebouwde Svelte) — als die er is.
# --------------------------------------------------------------------------

def _static_dir() -> Path:
    s = get_settings()
    if s.static_dir:
        return Path(s.static_dir)
    # backend/app/main.py -> repo-root/frontend/dist
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


_dist = _static_dir()
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")
else:
    @app.get("/", response_class=HTMLResponse)
    def _placeholder() -> str:
        return (
            "<!doctype html><meta charset='utf-8'>"
            "<body style='font-family:system-ui;background:#000;color:#eee;"
            "padding:2rem;line-height:1.5'>"
            "<h1>Life Dashboard — API draait</h1>"
            "<p>De frontend is nog niet gebouwd. Bouw 'm met "
            "<code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>, "
            "of open de API op <code>/docs</code>.</p>"
            f"<p>Frontend verwacht in: <code>{_dist}</code></p>"
            "</body>"
        )
