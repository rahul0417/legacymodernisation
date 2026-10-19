# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: BR-C-01, BR-C-02, BR-C-03, BR-C-04, BR-C-05, BR-C-06, BR-C-07, BR-C-08, BR-C-11
# LEGACY: source/index.php:6, source/addAction.php:37, source/editAction.php:27, source/delete.php:9, source/edit.php:9
# COMPONENT: modules/users/service
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""
UserService — business-logic layer for the users module.

No FastAPI imports here (Planning §1.3 firewall). The session is always
passed in by the router, keeping this class unit-testable with a
hand-rolled AsyncSession against in-memory SQLite.

Error contract:
  - UserNotFound        → router maps to 404
  - EmailAlreadyExists  → router maps to 409
  - SQLAlchemyError     → bubbles up; router/main map to 500

Self-collision handling (AC-11c) lives in `update_user`: when an
IntegrityError fires, we re-fetch the row by email and compare ids.
Same id → not a conflict (the caller submitted their own email and
didn't actually change anything). Different id → raise
EmailAlreadyExists.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .errors import EmailAlreadyExists, UserNotFound
from .models import User
from .schemas import UserCreate, UserUpdate


class UserService:
    """Async business-logic methods over the users table.

    Constructed once per process; injected into routes via Depends().
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger("crud.users.service")

    # ── BR-C-01 / BR-C-02 ─ list ────────────────────────────────────────────

    async def list_users(self, db: AsyncSession) -> list[User]:
        """Return every user, ordered strictly by `id` DESC (BR-C-01).

        Pure SELECT — no row is created/updated/deleted (BR-C-02). No
        pagination params; no filters; no alternate sort accepted in MVP.
        """
        stmt = select(User).order_by(User.id.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # ── BR-C-07 ─ get one ───────────────────────────────────────────────────

    async def get_user(self, user_id: int, db: AsyncSession) -> User:
        """Fetch a single user by surrogate id (BR-C-07).

        Raises `UserNotFound(user_id)` if no row matches.
        """
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise UserNotFound(user_id)
        return row

    # ── BR-C-03, 04, 05, 06, 11 ─ create ────────────────────────────────────

    async def create_user(self, payload: UserCreate, db: AsyncSession) -> User:
        """Insert a new user; translate UNIQUE violations to EmailAlreadyExists.

        Pydantic has already enforced BR-C-03/04/05/06 at the schema
        boundary by the time we get here. The remaining hazard is BR-C-11
        (email collision) — caught via IntegrityError on uq_users_email
        and re-raised as a domain exception so the router never sees a
        raw SQLAlchemy error.
        """
        user = User(
            name=payload.name,
            age=payload.age,
            email=payload.email,
        )
        db.add(user)
        try:
            await db.flush()  # forces UNIQUE check before commit
        except IntegrityError:
            await db.rollback()
            self._log_email_conflict("create", payload.email)
            raise EmailAlreadyExists(payload.email) from None

        await db.commit()
        await db.refresh(user)
        return user

    # ── BR-C-03..07, 11 ─ update ────────────────────────────────────────────

    async def update_user(
        self,
        user_id: int,
        payload: UserUpdate,
        db: AsyncSession,
    ) -> User:
        """Update an existing user's three editable columns.

        Preserves `id` (BR-C-07: path id is canonical; body-side `id`
        was already rejected by `extra="forbid"` on UserUpdate).

        AC-11c — self-collision: when an IntegrityError on
        uq_users_email fires, we re-fetch the row by email. If the
        clashing row IS the same user_id, the caller submitted their
        existing email unchanged — return the row, do NOT raise. If it
        is a different id, raise `EmailAlreadyExists`.
        """
        # Fetch via get_user — propagates UserNotFound on miss (AC-07a).
        user = await self.get_user(user_id, db)

        user.name = payload.name
        user.age = payload.age
        user.email = payload.email

        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            # Re-fetch by email to distinguish self-collision (AC-11c)
            # from genuine conflict (AC-11b). After rollback the session
            # has dropped the in-memory edits; query against the
            # persisted state.
            stmt = select(User).where(User.email == payload.email)
            result = await db.execute(stmt)
            other = result.scalar_one_or_none()
            if other is not None and other.id == user_id:
                # AC-11c: caller resubmitted own email — re-apply edits
                # on the freshly-loaded row and try again. Since name +
                # age may genuinely differ from the persisted row, do a
                # second flush. If it fails again, surface as 409 to
                # avoid an infinite loop (defensive).
                other.name = payload.name
                other.age = payload.age
                other.email = payload.email
                try:
                    await db.flush()
                except IntegrityError:
                    await db.rollback()
                    self._log_email_conflict("update-retry", payload.email)
                    raise EmailAlreadyExists(payload.email) from None
                await db.commit()
                await db.refresh(other)
                return other

            self._log_email_conflict("update", payload.email)
            raise EmailAlreadyExists(payload.email) from None

        await db.commit()
        await db.refresh(user)
        return user

    # ── BR-C-08 ─ delete ────────────────────────────────────────────────────

    async def delete_user(self, user_id: int, db: AsyncSession) -> None:
        """Hard-delete a user by id (BR-C-08).

        No soft-delete, no audit. `get_user` propagates 404 on miss.
        """
        user = await self.get_user(user_id, db)
        await db.delete(user)
        await db.commit()

    # ── helpers ─────────────────────────────────────────────────────────────

    def _log_email_conflict(self, op: str, email: str) -> None:
        """WARNING log with email scrubbed (Comprehension §8.2)."""
        try:
            local, _, domain = email.partition("@")
            scrubbed = f"{local[:1]}***@{domain}" if domain else "***"
        except Exception:  # noqa: BLE001 — logging must not raise
            scrubbed = "***@***"
        self.logger.warning(
            "email_unique_violation",
            extra={
                "event": "email_unique_violation",
                "op": op,
                "email_scrubbed": scrubbed,
            },
        )
