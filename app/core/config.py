from pydantic_settings import BaseSettings
from datetime import timedelta

class Settings(BaseSettings):
    SECRET_KEY: str = "replace_this_with_strong_random_secret"  # став в .env у проді
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    REFRESH_COOKIE_NAME: str = "refresh_token"
    REFRESH_COOKIE_SECURE: bool = False  # у проді True (HTTPS)
    REFRESH_COOKIE_SAMESITE: str = "lax"

    class Config:
        env_file = ".env"

settings = Settings()
