# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-01, BR-C-05, BR-C-07, BR-C-08, BR-C-10, BR-C-11, BR-C-12
# LEGACY: source/shorty.php:226-264, 311-394
# COMPONENT: modules/urls/service
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
UrlService — business-logic layer for the urls module.

No FastAPI imports here. The session is always passed in by the router,
keeping this class unit-testable with a hand-rolled AsyncSession against
in-memory SQLite. Background telemetry runs with an independent session
acquired from `self.session_factory` (Planning §7.3, OQ-P-01).

Error contract:
  - BadUrl           → router maps to 400  (user-submitted URL failed regex)
  - StoredUrlCorrupt → router maps to 500  (DB-loaded URL failed revalidation; OQ-C-02)
  - IpNotAllowed     → router maps to 403
  - UrlNotFound      → router maps to 404
  - EncodeOverflow   → router maps to 500
  - SQLAlchemyError  → router maps to 500
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from .encode import EncoderConfig, decode, encode
from .errors import BadUrl, StoredUrlCorrupt, UrlNotFound
from .models import Url
from .schemas import LEGACY_URL_REGEX, CreateUrlResult

_INT32_MAX = 2_147_483_647
_LEGACY_RE = re.compile(LEGACY_URL_REGEX)


class UrlService:
    """Async business-logic methods over the urls table.

    Constructed once per process; injected into routes via Depends().
    """

    def __init__(
        self,
        cfg: EncoderConfig,
        hostname: str,
        logger: logging.Logger,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.cfg = cfg
        self.hostname = hostname.rstrip("/")
        self.logger = logger
        self.session_factory = session_factory

    # ── public API ──────────────────────────────────────────────────────────

    async def create_or_get(self, url: str, db: AsyncSession) -> CreateUrlResult:
        """Insert-or-fetch a URL row and return its short-code result.

        BR-C-01 (idempotent), BR-C-02 (regex enforced by caller), BR-C-03
        (Starlette decoded once), BR-C-08 (caller decides fall-through),
        BR-C-11 (created timestamp comes from server default).

        Concurrency-safe via INSERT ... ON CONFLICT DO NOTHING RETURNING id;
        falls back to a SELECT when the row pre-existed.
        """
        stmt = (
            pg_insert(Url)
            .values(url=url)
            .on_conflict_do_nothing(index_elements=["url"])
            .returning(Url.id)
        )
        result = await db.execute(stmt)
        inserted_id = result.scalar_one_or_none()

        if inserted_id is None:
            existing = await db.execute(select(Url.id).where(Url.url == url))
            inserted_id = existing.scalar_one()
            was_created = False
        else:
            was_created = True

        # Service commits — router does not.
        await db.commit()

        code = encode(inserted_id, self.cfg)
        short_url = f"{self.hostname}/{code}"

        return CreateUrlResult(
            id=inserted_id,
            code=code,
            short_url=short_url,
            was_created=was_created,
        )

    async def lookup_and_redirect(self, code: str, db: AsyncSession) -> Url:
        """Resolve a short code to a Url row, fire telemetry, return the row.

        BR-C-05 (single-row read by decoded id), BR-C-06 (404 on miss),
        BR-C-07 (caller emits the redirect), BR-C-10 (fire-and-forget
        telemetry), and the OQ-C-03 decode-overflow defence.

        Steps:
          1. decode code → integer id; on ValueError → UrlNotFound.
          2. bounds-check id within INT32; out-of-range → UrlNotFound.
          3. SELECT row by id; missing → UrlNotFound.
          4. Re-validate stored URL against legacy regex (RF-06).
             If it fails, raise BadUrl (router emits 500 per OQ-C-02).
          5. Dispatch telemetry update as a background task (independent session).
          6. Return the Url row.
        """
        try:
            id_ = decode(code, self.cfg)
        except ValueError:
            raise UrlNotFound() from None

        if id_ < 1 or id_ > _INT32_MAX:
            # OQ-C-03: decode-overflow → 404 (do not leak schema details).
            raise UrlNotFound()

        result = await db.execute(select(Url).where(Url.id == id_))
        row: Optional[Url] = result.scalar_one_or_none()
        if row is None:
            raise UrlNotFound()

        # RF-06 / OQ-C-02 — re-validate before emitting Location.
        # StoredUrlCorrupt (not BadUrl) so router maps to HTTP 500: this is
        # data-integrity corruption, not client error.
        if _LEGACY_RE.match(row.url) is None:
            self.logger.error(
                "stored_url_failed_revalidation",
                extra={"id": row.id, "event": "stored_url_failed_revalidation"},
            )
            raise StoredUrlCorrupt()

        # BR-C-10 fire-and-forget telemetry.
        asyncio.create_task(self._record_hit(row.id))

        return row

    def build_short_url(self, id_: int) -> str:
        """Sync helper — `{hostname}/{encode(id)}`."""
        return f"{self.hostname}/{encode(id_, self.cfg)}"

    async def ping(self, db: AsyncSession) -> bool:
        """Liveness probe for R5 — runs `SELECT 1`.

        Returns True if the DB responded, False otherwise. Wraps the only
        place the router would otherwise need to import from sqlalchemy
        (preserving the §1.1 firewall: router ↛ sqlalchemy directly).
        """
        try:
            from sqlalchemy import text as _text  # local import: never at module level for router

            await db.execute(_text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False

    # ── private ─────────────────────────────────────────────────────────────

    async def _record_hit(self, id_: int) -> None:
        """Increment hits and stamp `accessed` for the given row.

        Runs in a background task with an INDEPENDENT session — the request
        session is closed by the time this fires (Planning §7.3 / OQ-P-01).
        Exceptions are logged at WARNING and swallowed so a redirect is
        never blocked by a telemetry failure (BR-C-10 fire-and-forget).
        """
        try:
            async with self.session_factory() as bg_db:
                stmt = (
                    update(Url)
                    .where(Url.id == id_)
                    .values(
                        hits=Url.hits + 1,  # DB-side increment — concurrency-safe
                        accessed=func.now(),
                    )
                )
                await bg_db.execute(stmt)
                await bg_db.commit()
        except SQLAlchemyError as exc:
            self.logger.warning(
                "telemetry_update_failed",
                extra={
                    "event": "telemetry_update_failed",
                    "id": id_,
                    "error": str(exc),
                },
            )
        except Exception as exc:  # noqa: BLE001 — fire-and-forget must not raise
            self.logger.warning(
                "telemetry_update_failed",
                extra={
                    "event": "telemetry_update_failed",
                    "id": id_,
                    "error": repr(exc),
                },
            )
