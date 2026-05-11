# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Database ─────────────────────────────────────────────────────────────
    # SQLite for dev/demo (default). Override with PostgreSQL via .env for prod.
    DATABASE_URL:      str = "sqlite+aiosqlite:///./rapidaid.db"
    SYNC_DATABASE_URL: str = "sqlite:///./rapidaid.db"

    # ── Security ─────────────────────────────────────────────────────────────
    SECRET_KEY:                    str = "dev-secret-key-change-in-production-32chars!!"
    ALGORITHM:                     str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES:   int = 1440  # 24 hours

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins. Spaces are stripped automatically.
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ── External APIs ─────────────────────────────────────────────────────────
    GROQ_API_KEY:   str = ""      # Groq API for LLaMA 3.3 Triage & reasoning (leave empty to use rule-based fallback)
    ORS_API_KEY:    str = "demo"  # OpenRouteService (for future turn-by-turn routing)

    # ── App Behaviour ─────────────────────────────────────────────────────────
    DEBUG:     bool = True   # SQLAlchemy echo + Uvicorn reload
    DEMO_MODE: bool = True   # Auto-seed demo data on startup
    APP_NAME:  str  = "RapidAid.ai"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins_list(self) -> list[str]:
        """Return ALLOWED_ORIGINS as a clean list (strips whitespace)."""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()
