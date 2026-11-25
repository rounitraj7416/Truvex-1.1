"""Application configuration loaded from environment variables."""

from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BASE_DIR.parent


class Settings(BaseSettings):
    """Typed application configuration."""

    model_config = SettingsConfigDict(
        env_file=(str(ROOT_DIR / ".env"), str(BASE_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "The Trust Layer"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    SECRET_KEY: str = Field(default="")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    COOKIE_SECURE: bool = False
    AUTH_COOKIE_NAME: str = "trust_layer_auth"
    CUSTOMER_SESSION_COOKIE_NAME: str = "trust_layer_customer_session"

    DATABASE_URL: str = f"sqlite:///{(ROOT_DIR / 'trust_layer.db').as_posix()}"

    TRUST_ID_EXPIRY_MINUTES: int = 5
    CUSTOMER_SESSION_EXPIRY_MINUTES: int = 30
    PUBLIC_RATE_LIMIT_PER_MINUTE: int = 30
    MAX_AUDIO_UPLOAD_BYTES: int = 10 * 1024 * 1024  # 10 MB

    AI_PROVIDER: str = "mock"
    MOCK_VOICE_PASS_THRESHOLD: float = 0.75
    MOCK_DEEPFAKE_MAX_RISK: float = 0.35

    DETECTIFAI_API_BASE_URL: str = "https://platform.detectif.ai"
    DETECTIFAI_API_KEY: str = ""

    SEED_ADMIN_EMAIL: str = "admin@trustlayer.demo"
    SEED_ADMIN_PASSWORD: str = ""

    def model_post_init(self, __context: object) -> None:
        if not self.SECRET_KEY or self.SECRET_KEY.startswith("replace-with"):
            if self.ENVIRONMENT.lower() == "production":
                raise RuntimeError(
                    "SECRET_KEY must be set to a strong secret in production."
                )
            # Ephemeral secret for local dev/testing when no .env secret is provided
            self.SECRET_KEY = secrets.token_urlsafe(48)
            logger.warning(
                "SECRET_KEY not configured in environment; generated an ephemeral "
                "key for this process."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
