# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: n/a — infrastructure (RF-008 fix: hardcoded creds → env)
# LEGACY: source/dbConnection.php:1-8
# COMPONENT: core/config
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""
Settings — Pydantic BaseSettings instance read once at startup.

Env-var prefix: CRUD_ (e.g. CRUD_DATABASE_URL, CRUD_CORS_ORIGINS).

RF-008 fix: legacy dbConnection.php hardcoded `root/root@localhost/test`.
Target reads everything from env via pydantic-settings. `.env.example`
ships the variable names; `.env` is git-ignored.

Gate-1 locks honoured:
  - DATABASE_URL default uses asyncpg driver (mandatory for async stack).
  - CORS_ORIGINS includes Vite dev server origin by default.
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the CRUD Users service.

    All fields are populated from environment variables (prefix `CRUD_`)
    or a `.env` file in the working directory. Field-level constraints
    enforce the basic invariants at construction time.
    """

    model_config = SettingsConfigDict(
        env_prefix="CRUD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = Field(
        default="postgresql+asyncpg://crud:crud@localhost:5432/crud",
        description=(
            "SQLAlchemy async DSN. Must use the asyncpg or aiosqlite driver."
        ),
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"],
        description="Allowed CORS origins (CSV in env; list in code).",
    )
    log_level: str = Field(default="INFO")
    api_prefix: str = Field(default="/api")
    version: str = Field(default="0.1.0")
    json_logs: bool = Field(default=False)
    db_echo: bool = Field(default=False)

    # ── Validators ──────────────────────────────────────────────────────────

    @field_validator("database_url")
    @classmethod
    def _validate_async_driver(cls, value: str) -> str:
        """Refuse sync drivers — async stack mandates asyncpg / aiosqlite."""
        if not (
            value.startswith("postgresql+asyncpg://")
            or value.startswith("sqlite+aiosqlite://")
        ):
            raise ValueError(
                "CRUD_DATABASE_URL must use 'postgresql+asyncpg://' "
                "or 'sqlite+aiosqlite://' (sync drivers are unsupported)."
            )
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value):
        """Allow CSV strings (env-var form) as well as list[str]."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value
