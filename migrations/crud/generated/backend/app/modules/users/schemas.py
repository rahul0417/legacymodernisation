# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: BR-C-03, BR-C-04, BR-C-05, BR-C-06, BR-C-07, BR-C-11
# LEGACY: source/addAction.php:13-31, source/editAction.php:7-25
# COMPONENT: modules/users/schemas
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""
Pydantic v2 request/response schemas for the users module.

No SQLAlchemy types leak — these schemas are DTOs only.

Constraints mirror Comprehension §4.2 verbatim. The Zod schema in
src/lib/schemas.ts is a 1:1 client-side mirror; any drift between
the two breaks BR-C-03/04/05/06 acceptance criteria.

ConfigDict(extra="forbid") on UserBase (and therefore UserCreate /
UserUpdate) enforces Gate-3 lock OQ-P-003: body-side `id` on PUT is
rejected with 422, never silently dropped.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Shared shape — `name`, `age`, `email` with all invariants."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Display name; whitespace stripped (BR-C-03, BR-C-06).",
    )
    age: int = Field(
        ...,
        ge=0,
        le=150,
        strict=True,
        description="Age in whole years; 0..150 inclusive (BR-C-04).",
    )
    email: EmailStr = Field(
        ...,
        max_length=100,
        description="RFC-5322-lite; globally unique (BR-C-05, BR-C-11).",
    )


class UserCreate(UserBase):
    """Request body for `POST /api/users`. No id."""

    pass


class UserUpdate(UserBase):
    """Request body for `PUT /api/users/{id}`.

    `id` comes from the path; `extra="forbid"` (inherited from UserBase)
    rejects any body-side `id` with HTTP 422 — Gate-3 lock OQ-P-003.
    """

    pass


class UserRead(UserBase):
    """Response body. `id` always present; assigned by DB."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        # `extra="ignore"` here (intentionally NOT forbid) — response side
        # is read-only; future fields can be added without breaking older
        # clients that round-trip the body.
    )

    id: int


class ProblemDetail(BaseModel):
    """RFC 9457 application/problem+json — error response envelope.

    Used by every non-2xx response from this service:
      - 404 → User not found
      - 409 → Email already exists
      - 422 → Validation error (with per-field `errors[]`)
      - 500 → Internal server error (catch-all; no stack-trace leakage)
    """

    model_config = ConfigDict(extra="allow")

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    errors: list[dict] | None = None


class HealthResponse(BaseModel):
    """Liveness probe response."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    service: Literal["crud"] = "crud"
    version: str
