# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: n/a — DI scaffolding
# LEGACY: n/a — scaffold (PHP relied on global $mysqli)
# COMPONENT: modules/users/dependencies
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""
FastAPI Depends() providers for the users module.

`get_settings`     — module-level singleton (built at startup).
`get_user_service` — module-level singleton UserService.
`set_settings`     — test hook; main.py also calls this from lifespan.
`init_user_service` — build + install the service singleton at startup.
"""

from __future__ import annotations

import logging

from app.core.config import Settings

from .service import UserService

_settings_singleton: Settings | None = None
_service_singleton: UserService | None = None


def set_settings(settings: Settings) -> None:
    """Install the application Settings (called from create_app lifespan)."""
    global _settings_singleton
    _settings_singleton = settings


def get_settings() -> Settings:
    """Return the live Settings singleton."""
    if _settings_singleton is None:
        raise RuntimeError("Settings not initialised — call set_settings first.")
    return _settings_singleton


def init_user_service() -> UserService:
    """Build and install the singleton UserService (called from lifespan)."""
    global _service_singleton
    _service_singleton = UserService(
        logger=logging.getLogger("crud.users.service"),
    )
    return _service_singleton


def get_user_service() -> UserService:
    """Return the singleton UserService."""
    if _service_singleton is None:
        raise RuntimeError(
            "UserService not initialised — call init_user_service first."
        )
    return _service_singleton
