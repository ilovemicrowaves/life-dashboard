"""Configuratie via env vars (en optioneel een .env-bestand in de CWD).

Alles wat per-omgeving verschilt staat hier. Paden, poort, OpenRouter-key en
reload-interval komen uit de omgeving zodat dev (Windows) en prod (NAS/Docker)
dezelfde code draaien met andere waarden.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Vault (bron van waarheid = een map met markdown) ---
    vault_path: Path = Path("./sample-vault")
    daily_subdir: str = "Daily"

    # --- Agenda-ingest (beide bronnen; bestand eerst) ---
    ics_file: str = ""  # .ics-bestand OF map met .ics-bestanden; leeg = uit
    ics_url: str = ""    # optionele live ICS-abonnement-URL

    # --- Index (herbouwbare cache, NIET de bron) ---
    index_db: Path = Path("./data/index.db")
    auto_rebuild_on_start: bool = True

    # --- Locale / tijd ---
    dashboard_tz: str = "Europe/Amsterdam"

    # --- AI-briefings via OpenRouter (provider-wisselbaar) ---
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-3.5-haiku"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_referer: str = "http://localhost"
    openrouter_title: str = "Life Dashboard"

    # --- Server / UI ---
    port: int = 8765
    reload_interval_hours: float = 3.0
    log_themes: str = "algemeen,werk,gezondheid,idee,relatie"
    default_theme: str = "algemeen"
    recent_logs_count: int = 10
    cors_origins: str = "*"

    # Statische frontend-build; leeg = afleiden t.o.v. de repo (../frontend/dist).
    static_dir: str = ""

    @property
    def daily_dir(self) -> Path:
        return self.vault_path / self.daily_subdir

    @property
    def themes_list(self) -> list[str]:
        items = [t.strip() for t in self.log_themes.split(",") if t.strip()]
        return items or [self.default_theme]

    @property
    def cors_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw == "*" or not raw:
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def reload_interval_ms(self) -> int:
        return int(self.reload_interval_hours * 3600 * 1000)


@lru_cache
def get_settings() -> Settings:
    return Settings()
