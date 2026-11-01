"""Application settings, loaded from environment variables (and a local .env file in development)."""

import os
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Render sets RENDER=true on every service, so production is detected without an env var.
    environment: Literal["development", "test", "production"] = Field(
        default_factory=lambda: "production" if os.getenv("RENDER") else "development"
    )

    # Supabase Postgres. Use the *Session pooler* connection string from Supabase (IPv4, port 5432).
    # A plain postgresql:// URL is accepted and converted to the asyncpg driver automatically.
    database_url: str = "sqlite+aiosqlite:///./oryne-dev.db"

    # Supabase Auth. New projects sign JWTs with asymmetric keys (verified via JWKS from SUPABASE_URL);
    # legacy projects use a shared HS256 secret - set SUPABASE_JWT_SECRET for those.
    supabase_url: str | None = None
    supabase_jwt_secret: str | None = None
    supabase_jwt_audience: str = "authenticated"

    # Comma-separated origins allowed to call the dashboard API (the Oryne dashboard itself).
    allowed_origins: str = "https://panel.oryne.org,http://localhost:5180"

    # Public URL of this API, used to build Daraja callback URLs (phase 2).
    # On Render this defaults to the service's own URL (RENDER_EXTERNAL_URL).
    public_base_url: str = Field(default_factory=lambda: os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000"))

    # Server-side secret mixed into API-key hashes, so a leaked database alone cannot be used to
    # verify guessed keys. Must be a long random value in production and never change afterwards.
    api_key_pepper: str = "dev-only-pepper-change-me"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url[len(prefix):]
        return url

    @property
    def is_postgres(self) -> bool:
        return self.async_database_url.startswith("postgresql+asyncpg://")

    @property
    def database_is_local(self) -> bool:
        host = urlparse(self.async_database_url.replace("+asyncpg", "")).hostname or ""
        return host in {"localhost", "127.0.0.1", ""}

    def validate_for_production(self) -> None:
        """Fail fast on unsafe production configuration."""
        if self.environment != "production":
            return
        problems = []
        if not self.is_postgres:
            problems.append("DATABASE_URL must point at Postgres")
        if not (self.supabase_url or self.supabase_jwt_secret):
            problems.append("SUPABASE_URL or SUPABASE_JWT_SECRET is required")
        if self.api_key_pepper.startswith("dev-") or len(self.api_key_pepper) < 32:
            problems.append("API_KEY_PEPPER must be a random value of at least 32 characters")
        if problems:
            raise RuntimeError("Invalid production configuration: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()
