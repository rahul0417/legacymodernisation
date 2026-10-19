# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: BR-C-01, BR-C-02, BR-C-07, BR-C-08, BR-C-09, BR-C-11
# LEGACY: source/index.php, source/addAction.php, source/editAction.php, source/delete.php, source/edit.php
# COMPONENT: modules/users/router
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""
FastAPI APIRouter for the users module — 5 endpoints.

Routes (Planning §7):
  GET    /api/users         → 200, list[UserRead], ORDER BY id DESC  (BR-C-01,02)
  POST   /api/users         → 201, UserRead, Location header         (BR-C-03..06,11)
  GET    /api/users/{id}    → 200, UserRead                          (BR-C-07)
  PUT    /api/users/{id}    → 200, UserRead                          (BR-C-03..07,11)
  DELETE /api/users/{id}    → 204 No Content                         (BR-C-08,09)

BR-C-09 (DELETE verb only): no GET endpoint exists for deletion. The
legacy `delete.php` was triggered by an HTTP GET — this router only
registers `@router.delete(...)` for removal, so a GET on the same path
returns FastAPI's default 405 Method Not Allowed (Comprehension §3
AC-09a interprets the legacy `/delete?id=...` URL as a missing route → 404
which is also achieved because the path itself does not exist).

Layer firewall: this module imports `AsyncSession` as a typing-only
surface from sqlalchemy.ext.asyncio — it never builds queries directly.
All SQL lives in UserService.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.ext.asyncio import AsyncSession  # typing-only surface

from app.db.engine import get_session

from .dependencies import get_user_service
from .schemas import UserCreate, UserRead, UserUpdate
from .service import UserService

router = APIRouter(prefix="/api/users", tags=["users"])


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/users — list (BR-C-01, BR-C-02)


@router.get(
    "",
    response_model=list[UserRead],
    status_code=status.HTTP_200_OK,
    summary="List all users (newest first).",
)
async def list_users_route(
    service: Annotated[UserService, Depends(get_user_service)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> list[UserRead]:
    """Return every user, sorted strictly by `id` DESC (BR-C-01).

    Side-effect-free (BR-C-02). Empty roster → `[]`, never `null`.
    """
    rows = await service.list_users(db)
    return [UserRead.model_validate(row) for row in rows]


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/users — create (BR-C-03..06, BR-C-11)


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user.",
)
async def create_user_route(
    payload: UserCreate,
    response: Response,
    service: Annotated[UserService, Depends(get_user_service)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> UserRead:
    """Insert a new user.

    Pydantic enforces BR-C-03/04/05/06. Service translates UNIQUE
    violations to EmailAlreadyExists → 409 (BR-C-11). On success sets
    `Location: /api/users/{id}` per REST hygiene.
    """
    row = await service.create_user(payload, db)
    response.headers["Location"] = f"/api/users/{row.id}"
    return UserRead.model_validate(row)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/users/{id} — read one (BR-C-07)


@router.get(
    "/{user_id}",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Fetch a single user by id.",
)
async def get_user_route(
    user_id: Annotated[int, Path(ge=1)],
    service: Annotated[UserService, Depends(get_user_service)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> UserRead:
    """Single-row read by surrogate id (BR-C-07)."""
    row = await service.get_user(user_id, db)
    return UserRead.model_validate(row)


# ─────────────────────────────────────────────────────────────────────────────
# PUT /api/users/{id} — update (BR-C-03..07, BR-C-11)


@router.put(
    "/{user_id}",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Replace an existing user's editable fields.",
)
async def update_user_route(
    user_id: Annotated[int, Path(ge=1)],
    payload: UserUpdate,
    service: Annotated[UserService, Depends(get_user_service)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> UserRead:
    """Update name/age/email; path id is canonical (BR-C-07).

    AC-11c self-collision (caller submits own email unchanged) → 200, not
    409. Genuine conflict (other user's email) → 409. UserService
    handles the distinction.
    """
    row = await service.update_user(user_id, payload, db)
    return UserRead.model_validate(row)


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /api/users/{id} — remove (BR-C-08, BR-C-09)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Permanently delete a user.",
)
async def delete_user_route(
    user_id: Annotated[int, Path(ge=1)],
    service: Annotated[UserService, Depends(get_user_service)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Hard-delete (BR-C-08); DELETE verb only (BR-C-09).

    A GET on this path resolves to a different route (`get_user_route`)
    not a delete — that is the desired REST-verb hygiene. Returns 204
    No Content with an empty body on success.
    """
    await service.delete_user(user_id, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
