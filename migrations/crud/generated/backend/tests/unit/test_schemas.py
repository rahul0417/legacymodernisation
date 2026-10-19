# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: BR-C-03, BR-C-04, BR-C-05, BR-C-06
# LEGACY: source/addAction.php:13-31, source/editAction.php:7-25
# COMPONENT: tests/unit/test_schemas
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""Pure Pydantic validation tests for UserCreate/UserUpdate/UserRead.

Stage 6 TestGen will enrich these with the full Planning §11.2 matrix.
This file ships the smoke layer: one passing case + one failing case
per BR-C-03..06.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.users.schemas import (
    ProblemDetail,
    UserCreate,
    UserRead,
    UserUpdate,
)


class TestUserCreateValidation:
    """BR-C-03/04/05/06 enforcement on POST /api/users body."""

    def test_BR_C_03_happy_path_accepts_all_fields(self):
        u = UserCreate(name="Alice", age=30, email="alice@example.com")
        assert u.name == "Alice"
        assert u.age == 30
        assert u.email == "alice@example.com"

    def test_BR_C_03_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            UserCreate(name="", age=30, email="a@b.co")

    def test_BR_C_03_whitespace_only_name_rejected(self):
        # str_strip_whitespace=True + min_length=1 → "   " → "" → reject
        with pytest.raises(ValidationError):
            UserCreate(name="   ", age=30, email="a@b.co")

    def test_BR_C_04_age_negative_rejected(self):
        with pytest.raises(ValidationError):
            UserCreate(name="Alice", age=-1, email="a@b.co")

    def test_BR_C_04_age_above_150_rejected(self):
        with pytest.raises(ValidationError):
            UserCreate(name="Alice", age=151, email="a@b.co")

    def test_BR_C_04_age_zero_accepted(self):
        u = UserCreate(name="Newborn", age=0, email="x@y.co")
        assert u.age == 0

    def test_BR_C_04_age_150_accepted(self):
        u = UserCreate(name="Methuselah", age=150, email="x@y.co")
        assert u.age == 150

    def test_BR_C_04_age_float_rejected_strict(self):
        # strict=True → no float coercion
        with pytest.raises(ValidationError):
            UserCreate(name="Alice", age=30.5, email="a@b.co")

    def test_BR_C_05_invalid_email_rejected(self):
        with pytest.raises(ValidationError):
            UserCreate(name="Alice", age=30, email="not-an-email")

    def test_BR_C_06_name_too_long_rejected(self):
        with pytest.raises(ValidationError):
            UserCreate(name="x" * 101, age=30, email="a@b.co")

    def test_BR_C_06_name_exactly_100_accepted(self):
        u = UserCreate(name="x" * 100, age=30, email="a@b.co")
        assert len(u.name) == 100


class TestUserUpdateExtraForbid:
    """Gate-3 lock OQ-P-003 — body-side `id` on PUT is rejected (extra=forbid)."""

    def test_body_id_rejected_with_422(self):
        with pytest.raises(ValidationError):
            UserUpdate(
                id=999,
                name="Alice",
                age=30,
                email="a@b.co",
            )  # type: ignore[call-arg]


class TestUserReadFromAttributes:
    """UserRead should construct from any object with the right attrs."""

    def test_from_attributes_accepts_namedtuple_like(self):
        # Pydantic v2's `from_attributes=True` walks an INSTANCE's attributes
        # (not a class object). Provide an instance so the test matches the
        # SQLAlchemy ORM row path that UserRead.model_validate(user) takes.
        class Row:
            id = 1
            name = "Alice"
            age = 30
            email = "alice@example.com"

        u = UserRead.model_validate(Row())
        assert u.id == 1
        assert u.email == "alice@example.com"


class TestProblemDetailEnvelope:
    """ProblemDetail must accept the canonical fields with sensible defaults."""

    def test_default_type_is_about_blank(self):
        p = ProblemDetail(title="X", status=404)
        assert p.type == "about:blank"

    def test_errors_field_accepts_list_of_dicts(self):
        p = ProblemDetail(
            title="Validation error",
            status=422,
            errors=[{"loc": ["body", "age"], "msg": "ge", "type": "ge"}],
        )
        assert p.errors and p.errors[0]["loc"] == ["body", "age"]
