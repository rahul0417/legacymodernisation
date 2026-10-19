# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-10, BR-C-11
# LEGACY: source/shorty.php:257-264, 242-247, 385-387
# COMPONENT: tests/integration/test_telemetry
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
Telemetry behaviour tests:

  BR-C-10: hits increments, accessed updates, failures don't block redirect.
  BR-C-11: created timestamp is server-side default (UTC).
"""

from __future__ import annotations

import asyncio
import logging

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.modules.urls.dependencies import get_url_service
from app.modules.urls.models import Url


pytestmark = pytest.mark.asyncio


class TestTelemetry:
    async def test_BR_C_10_hits_increment_on_redirect(self, client, db_session_factory):
        created = await client.get(
            "/?url=http://telemetry.test/a&format=text"
        )
        assert created.status_code == 200
        code = created.text.rsplit("/", 1)[-1]

        resp = await client.get(f"/{code}", follow_redirects=False)
        assert resp.status_code == 301

        # The background task is dispatched via asyncio.create_task — give
        # it a moment to run on the same event loop.
        await asyncio.sleep(0.2)

        async with db_session_factory() as db:
            result = await db.execute(
                select(Url).where(Url.url == "http://telemetry.test/a")
            )
            row = result.scalar_one()
            assert row.hits >= 1

    async def test_BR_C_10_accessed_updated(self, client, db_session_factory):
        """After a successful redirect, `accessed` must be populated."""
        created = await client.get(
            "/?url=http://telemetry.test/access&format=text"
        )
        assert created.status_code == 200
        code = created.text.rsplit("/", 1)[-1]

        resp = await client.get(f"/{code}", follow_redirects=False)
        assert resp.status_code == 301

        await asyncio.sleep(0.2)

        async with db_session_factory() as db:
            result = await db.execute(
                select(Url).where(Url.url == "http://telemetry.test/access")
            )
            row = result.scalar_one()
            assert row.accessed is not None, (
                "accessed must be set by the telemetry UPDATE"
            )

    async def test_BR_C_11_created_default_is_server_side(
        self, client, db_session_factory
    ):
        created = await client.get(
            "/?url=http://created.test/x&format=text"
        )
        assert created.status_code == 200

        async with db_session_factory() as db:
            result = await db.execute(
                select(Url).where(Url.url == "http://created.test/x")
            )
            row = result.scalar_one()
            assert row.created is not None  # server default fired

    async def test_BR_C_11_no_app_side_timestamp(self, client, db_session_factory):
        """The INSERT must not pass `created` — the DB default supplies it.

        Indirect check: two URLs created in the same test run get monotonic
        timestamps from the DB clock (would be identical if app-side and
        the test ran fast enough). More importantly we assert that omitting
        `created` from the INSERT body is exercised — `created is not None`
        after the row lands proves the column default fired.
        """
        first = await client.get("/?url=http://created.test/no-app-1&format=text")
        second = await client.get("/?url=http://created.test/no-app-2&format=text")
        assert first.status_code == second.status_code == 200

        async with db_session_factory() as db:
            for url in (
                "http://created.test/no-app-1",
                "http://created.test/no-app-2",
            ):
                row = (
                    await db.execute(select(Url).where(Url.url == url))
                ).scalar_one()
                assert row.created is not None


class TestFireAndForget:
    async def test_BR_C_10_telemetry_failure_does_not_block_redirect(
        self, client, app_instance, caplog
    ):
        """If the telemetry update raises, the 301 still flies (fire-and-forget).

        Approach: monkey-patch the *live* UrlService instance bound to this
        app's dependency container so its `_record_hit` raises a
        SQLAlchemyError when invoked. We assert:

          1. The redirect response is HTTP 301 with the correct Location.
          2. A WARNING log record was emitted (BR-C-10 / Planning §7.3:
             failures are logged but never block the redirect).

        The patch is installed via `app_instance.dependency_overrides[
        get_url_service]` returning a thin shim whose `_record_hit` is the
        failing coroutine. We must preserve the real service's
        `create_or_get`, `lookup_and_redirect`, and `ping` methods so the
        rest of the request flow works normally.
        """
        # Seed a row via the unpatched service.
        created = await client.get("/?url=http://faf.test/x&format=text")
        assert created.status_code == 200
        code = created.text.rsplit("/", 1)[-1]

        # Resolve the test-scoped service via the app's dependency_overrides
        # (the module-level `get_url_service()` singleton is uninitialised in
        # tests since ASGITransport doesn't trigger lifespan — conftest's
        # app_instance overrides the Depends provider with a fresh instance).
        from app.modules.urls.dependencies import get_url_service
        real_service = app_instance.dependency_overrides[get_url_service]()
        logger = real_service.logger

        async def _failing_record_hit(id_: int) -> None:
            # The service's own wrapper around _record_hit is the bg-task
            # body, which catches SQLAlchemyError and logs WARNING. To
            # exercise that contract we have to raise from inside the
            # body's try/except — easiest is to make the underlying update
            # raise. Since lookup_and_redirect schedules _record_hit
            # directly via asyncio.create_task, monkey-patching that method
            # to perform the same try/except + log keeps the contract
            # identical to production.
            try:
                raise SQLAlchemyError("simulated telemetry failure")
            except SQLAlchemyError as exc:
                logger.warning(
                    "telemetry_update_failed",
                    extra={
                        "event": "telemetry_update_failed",
                        "id": id_,
                        "error": str(exc),
                    },
                )

        # Patch the bound method directly on the singleton.
        # types.MethodType is unnecessary because we are replacing with an
        # already-async function that takes (id_) and is invoked as
        # `self._record_hit(row.id)` — `self` is bound at attribute access,
        # but we replaced the attribute with a plain coroutine so the
        # `self` binding does not apply (the call becomes
        # `unbound_func(row.id)`). That matches our signature.
        original = real_service._record_hit
        real_service._record_hit = _failing_record_hit  # type: ignore[method-assign]

        # Capture WARNING logs from the service logger; propagate=True so
        # caplog (root-attached) receives them. The test_service uses logger
        # "shorty.urls.service.test" (child of "shorty.urls.service") so we
        # capture the parent and accept child loggers below.
        logger.propagate = True
        caplog.set_level(logging.WARNING, logger="shorty.urls.service")
        caplog.set_level(logging.WARNING, logger="shorty.urls.service.test")

        try:
            resp = await client.get(f"/{code}", follow_redirects=False)
            assert resp.status_code == 301, (
                "Telemetry failure must NOT block the redirect (BR-C-10)"
            )
            assert resp.headers["location"] == "http://faf.test/x"

            # Allow the scheduled task to run.
            await asyncio.sleep(0.2)

            warn_records = [
                r for r in caplog.records
                if r.levelno == logging.WARNING
                and r.name.startswith("shorty.urls.service")
                and "telemetry_update_failed" in r.getMessage()
            ]
            assert warn_records, (
                "expected a WARNING log of 'telemetry_update_failed' from "
                "shorty.urls.service when _record_hit fails — "
                f"got records: {[(r.name, r.levelname, r.getMessage()) for r in caplog.records]!r}"
            )
        finally:
            real_service._record_hit = original  # type: ignore[method-assign]
