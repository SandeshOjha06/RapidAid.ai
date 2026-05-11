from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # Use SQLite for development/testing, PostgreSQL for production
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost/rapidaid"
    SYNC_DATABASE_URL: str = "postgresql://postgres:password@localhost/rapidaid"
    SECRET_KEY: str = "dev-secret-key-change-in-production-32chars!!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    ORS_API_KEY: str = "demo"
    DEBUG: bool = True
    DEMO_MODE: bool = True
    APP_NAME: str = "RapidAid.ai"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
