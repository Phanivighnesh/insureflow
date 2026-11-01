"""Runtime settings from environment variables (never hard-code secrets).

Dotenv loading: if python-dotenv is installed and a .env file exists in the project root,
it is loaded WITHOUT overriding existing environment variables. This means real environment
variables (e.g. set in CI/CD) always take precedence.
"""
from __future__ import annotations
import os

# Load .env if python-dotenv is available (never overrides real env vars)
try:
    from dotenv import load_dotenv
    _candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", ".env"),       # backend/.env
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"), # repo root .env
        os.path.abspath(".env"),                                           # current working directory .env
    ]
    for _env_file in _candidates:
        if os.path.exists(_env_file):
            load_dotenv(_env_file, override=False)
except ImportError:
    pass  # python-dotenv not installed — use environment variables directly


from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.environ.get("DATABASE_URL", "sqlite:///./insureflow.db")
    groq_api_key: str | None = os.environ.get("GROQ_API_KEY") or None
    groq_model: str = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
    cors_origins: str = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
    default_seed: int = int(os.environ.get("DEFAULT_SEED", "20261022"))
    # DEMO-ENVIRONMENT auth. Override in any shared deployment.
    session_secret: str = os.environ.get("SESSION_SECRET", "dev-only-insecure-secret-change-me")
    staff_access_code: str = os.environ.get("STAFF_ACCESS_CODE", "insureflow-demo")
    session_ttl_hours: int = int(os.environ.get("SESSION_TTL_HOURS", "12"))
    data_dir: str = os.environ.get("DATA_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")))
    # AI Copilot settings
    ai_timeout_seconds: float = float(os.environ.get("AI_TIMEOUT_SECONDS", "20"))
    ai_rate_limit_per_minute: int = int(os.environ.get("AI_RATE_LIMIT_PER_MINUTE", "20"))
    ai_rate_limit_window_seconds: int = int(os.environ.get("AI_RATE_LIMIT_WINDOW_SECONDS", "60"))
    ai_enabled: bool = os.environ.get("AI_ENABLED", "true").lower() not in ("false", "0", "no")


settings = Settings()
