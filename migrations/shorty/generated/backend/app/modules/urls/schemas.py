# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-02, BR-C-09
# LEGACY: source/shorty.php:332, 347-366
# COMPONENT: modules/urls/schemas
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
Pydantic v2 request/response schemas for the urls module.

No SQLAlchemy types leak — these schemas are DTOs only.
The legacy URL regex is preserved verbatim for parity (Gate 1 OQ-05).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# Legacy regex, preserved character-for-character from shorty.php:332.
# `\w+` matches [A-Za-z0-9_]+ — does NOT match dots, so e.g. "192.168.1.1"
# is rejected at this layer (documented oddity, BR-C-02).
LEGACY_URL_REGEX = r"^http[s]?://\w+"


class OutputFormat(StrEnum):
    """Response-format enum for create endpoints (BR-C-09)."""

    TEXT = "text"
    JSON = "json"
    XML = "xml"
    HTML = "html"

    @classmethod
    def parse(cls, raw: str | None) -> "OutputFormat":
        """Case-insensitive parse; unknown / None → HTML (default per BR-C-09)."""
        if raw is None:
            return cls.HTML
        lowered = raw.lower()
        for member in cls:
            if member.value == lowered:
                return member
        return cls.HTML


class CreateUrlRequest(BaseModel):
    """JSON body for `POST /shorten` (R4)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    # TODO(stage5-review): legacy regex retained for parity (Gate 1 OQ-05); strict validation Phase 5
    url: Annotated[
        str,
        Field(..., min_length=1, max_length=2048, pattern=LEGACY_URL_REGEX),
    ]
    format: Annotated[str | None, Field(default=None, max_length=16)] = None


class CreateUrlResult(BaseModel):
    """Internal service-layer return value (not a response model)."""

    model_config = ConfigDict(frozen=True)

    id: int
    code: str
    short_url: str
    was_created: bool  # True if INSERT happened, False if pre-existing (BR-C-01)


class JsonCreateResponse(BaseModel):
    """Response model for `?format=json` (BR-C-09)."""

    model_config = ConfigDict(extra="forbid")

    url: str


class ProblemDetail(BaseModel):
    """RFC 9457 lite — error response body shape."""

    model_config = ConfigDict(extra="ignore")

    detail: str
    type: str | None = None


class HealthResponse(BaseModel):
    """Liveness probe response (R5)."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "degraded"]
    db: Literal["ok", "down"]
