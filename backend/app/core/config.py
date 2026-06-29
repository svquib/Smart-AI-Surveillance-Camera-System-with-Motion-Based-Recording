"""Application configuration.

All settings are loaded from environment variables (and an optional `.env`
file) via Pydantic Settings. This keeps secrets out of the codebase and makes
the app portable across local / Docker / cloud environments.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = .../backend
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "Smart AI Surveillance System"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # --- Security (used from Phase 7 onward) ---
    SECRET_KEY: str = Field(default="change-me-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    JWT_ALGORITHM: str = "HS256"

    # --- Database (used from Phase 8 onward) ---
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'surveillance.db'}"
    # Create tables on startup. Fine for dev; turn OFF once Alembic owns the
    # schema so migrations aren't silently bypassed.
    AUTO_CREATE_TABLES: bool = True

    # --- Storage ---
    STORAGE_DIR: Path = BASE_DIR.parent / "storage"
    RECORDINGS_DIR: Path = BASE_DIR.parent / "storage" / "recordings"
    SNAPSHOTS_DIR: Path = BASE_DIR.parent / "storage" / "snapshots"

    # --- Camera / Vision (used from Phase 2 onward) ---
    DEFAULT_CAMERA_SOURCE: str = "0"  # "0" = laptop webcam, or an RTSP URL
    MOTION_THRESHOLD: int = 5000
    PRE_BUFFER_SECONDS: int = 5

    # --- Notifications (used from Phase 10 onward) ---
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — import this everywhere instead of Settings()."""
    return Settings()


settings = get_settings()
