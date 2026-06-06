"""Zentrale App-Konfiguration via pydantic-settings.

Liest Werte aus Umgebungsvariablen bzw. einer `.env`-Datei. API-Keys und
Secrets gehören ausschließlich hierher / in die `.env` — niemals in den Code
(siehe Abschnitt 10 des Specs).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_name: str = "Proaktiver Alltags-Copilot"
    debug: bool = False

    # --- Datenbank ---
    # SQLite im MVP; spätere Migration zu Postgres nur über diese URL.
    database_url: str = "sqlite:///./copilot.db"

    # --- Anthropic Claude API (Schritt 5) ---
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"

    # --- Telegram Bot (Schritt 2) ---
    telegram_bot_token: str = ""

    # --- Google Calendar (Schritt 4, read-only) ---
    google_client_id: str = ""
    google_client_secret: str = ""
    google_calendar_id: str = "primary"
    # Datei, in der das OAuth-Token (inkl. Refresh-Token) abgelegt wird.
    # Gitignored — enthält Zugangsdaten.
    google_token_file: str = "token.json"

    # --- Standard-Zeitzone ---
    default_timezone: str = "Europe/Berlin"


@lru_cache
def get_settings() -> Settings:
    """Liefert eine gecachte Settings-Instanz (einmal pro Prozess)."""
    return Settings()
