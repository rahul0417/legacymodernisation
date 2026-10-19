# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: BR-C-01, BR-C-07, BR-C-08, BR-C-11
# LEGACY: source/index.php:6, source/editAction.php:27, source/delete.php:9
# COMPONENT: tests/unit/test_service
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""Direct UserService tests against the per-test SQLite session.

Stage 6 TestGen will expand these into the full unit matrix (incl.
mocked AsyncSession edge cases). For now we run against the real
in-memory SQLite to lock the happy + sad paths.
"""

from __future__ import annotations

import logging

import pytest

from app.modules.users.errors import EmailAlreadyExists, UserNotFound
from app.modules.users.schemas import UserCreate, UserUpdate
from app.modules.users.service import UserService

pytestmark = pytest.mark.asyncio


def _svc() -> UserService:
    return UserService(logger=logging.getLogger("crud.users.service.test"))


class TestListUsers:
    async def test_BR_C_01_list_empty(self, db_session):
        rows = await _svc().list_users(db_session)
        assert rows == []

    async def test_BR_C_01_order_by_id_desc(self, db_session, seeded_users):
        rows = await _svc().list_users(db_session)
        ids = [r.id for r in rows]
        assert ids == sorted(ids, reverse=True), (
            f"BR-C-01 violation: ids not strictly descending → {ids}"
        )


class TestGetUser:
    async def test_BR_C_07_existing(self, db_session, seeded_users):
        target = seeded_users[0]
        row = await _svc().get_user(target.id, db_session)
        assert row.id == target.id

    async def test_BR_C_07_missing_raises(self, db_session):
        with pytest.raises(UserNotFound):
            await _svc().get_user(99999, db_session)


class TestCreateUser:
    async def test_happy_path(self, db_session):
        payload = UserCreate(name="Dora", age=25, email="dora@example.com")
        row = await _svc().create_user(payload, db_session)
        assert row.id >= 1
        assert row.email == "dora@example.com"

    async def test_BR_C_11_duplicate_email_raises(self, db_session, seeded_users):
        dup_email = seeded_users[0].email
        payload = UserCreate(name="Imposter", age=40, email=dup_email)
        with pytest.raises(EmailAlreadyExists):
            await _svc().create_user(payload, db_session)


class TestUpdateUser:
    async def test_happy_path(self, db_session, seeded_users):
        target = seeded_users[0]
        payload = UserUpdate(name="Alice Updated", age=31, email=target.email)
        row = await _svc().update_user(target.id, payload, db_session)
        assert row.name == "Alice Updated"
        assert row.age == 31

    async def test_BR_C_07_missing_raises(self, db_session):
        payload = UserUpdate(name="X", age=1, email="x@y.co")
        with pytest.raises(UserNotFound):
            await _svc().update_user(99999, payload, db_session)

    async def test_AC_11c_self_collision_returns_200(self, db_session, seeded_users):
        """Same user's existing email → not a conflict."""
        target = seeded_users[0]
        payload = UserUpdate(name="Alice Renamed", age=32, email=target.email)
        row = await _svc().update_user(target.id, payload, db_session)
        assert row.id == target.id
        assert row.name == "Alice Renamed"

    async def test_AC_11b_other_user_email_raises(self, db_session, seeded_users):
        """Other user's email → genuine conflict."""
        target = seeded_users[0]
        other_email = seeded_users[1].email
        payload = UserUpdate(name="Squatter", age=40, email=other_email)
        with pytest.raises(EmailAlreadyExists):
            await _svc().update_user(target.id, payload, db_session)


class TestDeleteUser:
    async def test_BR_C_08_happy(self, db_session, seeded_users):
        target = seeded_users[0]
        await _svc().delete_user(target.id, db_session)
        with pytest.raises(UserNotFound):
            await _svc().get_user(target.id, db_session)

    async def test_BR_C_08_missing_raises(self, db_session):
        with pytest.raises(UserNotFound):
            await _svc().delete_user(99999, db_session)
