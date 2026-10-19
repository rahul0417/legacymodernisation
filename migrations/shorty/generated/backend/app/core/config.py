# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-04, BR-C-09, BR-C-12
# LEGACY: source/config.php, source/shorty.php:328-330
# COMPONENT: core/config
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
Settings — Pydantic BaseSettings instance read once at startup.

Env-var prefix: SHORTY_ (e.g. SHORTY_HOSTNAME, SHORTY_DB_URL).
Validation runs at instantiation; a misconfigured encoder MUST fail loud
at import time rather than silently produce mismatched codes.

Gate 1 lock: salt="", padding=3, default 62-char alphabet.
RF-12 fix: padding default is 3 (matches config.php), not 1.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from app.modules.urls.encode import EncoderConfig


_DEFAULT_CHARS = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
)


class Settings(BaseSettings):
    """Runtime configuration for the Shorty service.

    All fields are populated from environment variables (prefix `SHORTY_`)
    or a `.env` file in the working directory. Field-level constraints +
    `model_validator(mode="after")` enforce the encoder invariants I-1..I-9
    at construction time.
    """

    model_config = SettingsConfigDict(
        env_prefix="SHORTY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # The IP_WHITELIST / TRUSTED_PROXIES fields are populated by
        # populate_by_name + alias so they match the documented env names.
        populate_by_name=True,
    )

    hostname: str = Field(default="http://localhost:8000")
    db_url: str = Field(
        default="postgresql+asyncpg://shorty:shorty@localhost:5432/shorty",
    )
    chars: str = Field(default=_DEFAULT_CHARS, min_length=2, max_length=128)
    salt: SecretStr = Field(default=SecretStr(""))
    padding: int = Field(default=3, ge=0, le=16)

    # CSV — parsed into frozensets by the properties below.
    ip_whitelist_raw: str = Field(default="", alias="SHORTY_IP_WHITELIST")
    trusted_proxies_raw: str = Field(
        default="127.0.0.1", alias="SHORTY_TRUSTED_PROXIES"
    )

    log_level: str = Field(default="INFO")
    json_logs: bool = Field(default=False)
    db_echo: bool = Field(default=False)

    # ── Validators ──────────────────────────────────────────────────────────

    @model_validator(mode="after")
    def _validate_chars_unique(self) -> "Settings":
        """Invariants I-1: chars must be unique and length >= 2."""
        if len(set(self.chars)) != len(self.chars):
            raise ValueError(
                "SHORTY_CHARS must contain unique characters "
                "(invariant I-1; changing chars after deploy breaks every URL)"
            )
        return self

    # ── Derived views ───────────────────────────────────────────────────────

    @property
    def ip_whitelist(self) -> frozenset[str]:
        """OQ-C-01: split on `,`, strip each entry, drop empties.

        Empty result = open mode (every IP allowed). Matches PHP
        `array_filter` semantics — a stray `","` yields the empty set.
        """
        return _csv_to_frozenset(self.ip_whitelist_raw)

    @property
    def trusted_proxies(self) -> frozenset[str]:
        """CSV of IPs whose `X-Forwarded-For` headers we honour (RF-05 fix)."""
        return _csv_to_frozenset(self.trusted_proxies_raw)

    @property
    def salt_value(self) -> str:
        """Unwrap the SecretStr — used only inside encode/decode (never logged)."""
        return self.salt.get_secret_value()

    @property
    def encoder_config(self) -> "EncoderConfig":
        """Build the immutable EncoderConfig the urls module consumes."""
        # Import here to keep this module free of urls.encode at import time
        # (pure-stdlib invariant for that module).
        from app.modules.urls.encode import EncoderConfig

        return EncoderConfig(
            chars=self.chars,
            salt=self.salt_value,
            padding=self.padding,
        )


# ── Helpers ────────────────────────────────────────────────────────────────


def _csv_to_frozenset(raw: str) -> frozenset[str]:
    """Split CSV, strip, drop empty entries. Empty result = open."""
    if not raw:
        return frozenset()
    parts = (entry.strip() for entry in raw.split(","))
    return frozenset(p for p in parts if p)
