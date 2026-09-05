from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from datetime import timedelta

class Settings(BaseSettings):
    SECRET_KEY: str
    DATABASE_URL: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    REFRESH_COOKIE_NAME: str = "refresh_token"
    REFRESH_COOKIE_SECURE: bool = False  # у проді True (HTTPS)
    REFRESH_COOKIE_SAMESITE: str = "lax"

    ADMIN_PASSWORD: str

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env"
    )

settings = Settings()
