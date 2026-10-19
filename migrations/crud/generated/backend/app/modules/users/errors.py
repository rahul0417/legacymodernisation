# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: BR-C-07, BR-C-11
# LEGACY: source/editAction.php:27 (silent UPDATE), source/delete.php:9 (silent DELETE)
# COMPONENT: modules/users/errors
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""
Domain exception hierarchy for the users module.

Service raises these; FastAPI exception handlers in `app.main` catch
them and translate into RFC-9457 ProblemDetail envelopes (Planning §7.6).

Replaces legacy PHP's silent SQL failures (delete.php:9 issues a DELETE
on a possibly-injected id with no error path) and silent success
messages with structured, testable exception objects.
"""

from __future__ import annotations


class UsersError(Exception):
    """Base class for all domain-specific errors in the users module."""

    title: str = "Internal error"
    status: int = 500
    detail: str | None = None


class UserNotFound(UsersError):
    """No row matches the given `user_id`.

    Raised by `UserService.get_user`, `update_user`, `delete_user`
    (BR-C-07: missing user → 404; BR-C-08: delete on non-existent id → 404).
    """

    title = "User not found"
    status = 404

    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        self.detail = f"User {user_id} not found"
        super().__init__(self.detail)


class EmailAlreadyExists(UsersError):
    """Email collides with an existing row's unique constraint.

    Raised by `UserService.create_user` and `update_user` after
    `IntegrityError` on `uq_users_email`. BR-C-11.

    Per AC-11c, `update_user` distinguishes self-collision (same id, no
    change → 200) from genuine conflict (other id → 409). This exception
    is therefore raised ONLY in the genuine-conflict case.
    """

    title = "Email already exists"
    status = 409

    def __init__(self, email: str) -> None:
        self.email = email
        # Quote the email so the message is unambiguous; logging in the
        # service layer must scrub PII before WARNING.
        self.detail = f"Email '{email}' is already registered."
        super().__init__(self.detail)
