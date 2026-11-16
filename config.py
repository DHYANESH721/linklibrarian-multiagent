"""Application configuration.

All settings are read from environment variables (loaded from a local `.env`
file by python-dotenv). Nothing secret is ever hardcoded here.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load .env once, at import time, before any Config attribute is read.
load_dotenv(BASE_DIR / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    """Parse a truthy environment string."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    """Parse an integer environment string, falling back on bad input."""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


class Config:
    """Base configuration shared by every environment."""

    # --- Flask ---
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    DEBUG = _as_bool(os.getenv("FLASK_DEBUG"), False)
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = _as_int(os.getenv("PORT"), 5000)

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'linklibrarian.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- AI provider (Groq: free tier, OpenAI-compatible) ---
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
    AI_MODEL = os.getenv("AI_MODEL", "llama-3.3-70b-versatile")
    AI_BASE_URL = os.getenv(
        "AI_BASE_URL", "https://api.groq.com/openai/v1/chat/completions"
    )
    AI_TIMEOUT = _as_int(os.getenv("AI_TIMEOUT"), 45)

    # --- Scraper ---
    SCRAPER_TIMEOUT = _as_int(os.getenv("SCRAPER_TIMEOUT"), 15)
    SCRAPER_MAX_CHARS = _as_int(os.getenv("SCRAPER_MAX_CHARS"), 12000)
    USER_AGENT = os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 LinkLibrarian/1.0",
    )

    @classmethod
    def ai_enabled(cls) -> bool:
        """True when an API key is present, so the app can degrade gracefully."""
        return bool(cls.GROQ_API_KEY)


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}


def get_config() -> type[Config]:
    """Return the config class named by APP_ENV (default: development)."""
    return CONFIG_MAP.get(os.getenv("APP_ENV", "development").lower(), DevelopmentConfig)
