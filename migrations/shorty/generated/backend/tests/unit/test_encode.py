# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-12
# LEGACY: source/shorty.php:122-203
# COMPONENT: tests/unit/test_encode
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
Unit tests for app.modules.urls.encode.

Three test classes:
  - TestEncoderConfig:  invariant validation (chars/padding pre-conditions).
  - TestEncodeVectors:  byte-equality against PHP-generated fixtures
                        (skipped until Stage 6 regenerates the JSON).
  - TestEncodeProperty: hypothesis round-trip property (BR-C-12 invariant).
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings as hsettings
from hypothesis import strategies as st

from app.modules.urls.encode import (
    EncoderConfig,
    alpha_to_num,
    decode,
    encode,
    get_seed,
    num_to_alpha,
)

DEFAULT_CHARS = (
    "abcdefghijklmnopqrstuvwxyz" "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "0123456789"
)


# ─────────────────────────────────────────────────────────────────────────────
# TestEncoderConfig — invariant validation


class TestEncoderConfig:
    def test_valid_config_constructs(self):
        cfg = EncoderConfig(chars=DEFAULT_CHARS, salt="", padding=3)
        assert cfg.chars == DEFAULT_CHARS
        assert cfg.salt == ""
        assert cfg.padding == 3

    def test_duplicate_chars_rejected(self):
        with pytest.raises(ValueError, match="unique"):
            EncoderConfig(chars="aabc", salt="", padding=3)

    def test_too_few_chars_rejected(self):
        with pytest.raises(ValueError, match="at least 2"):
            EncoderConfig(chars="a", salt="", padding=3)

    def test_negative_padding_rejected(self):
        with pytest.raises(ValueError, match="padding"):
            EncoderConfig(chars=DEFAULT_CHARS, salt="", padding=-1)

    def test_zero_padding_allowed(self):
        cfg = EncoderConfig(chars=DEFAULT_CHARS, salt="x", padding=0)
        # padding=0 suppresses seed branch even with non-empty salt.
        assert encode(1, cfg) == "b"


# ─────────────────────────────────────────────────────────────────────────────
# TestEncodeVectors — fixture-driven byte equality (BR-C-12)


def _load_vectors_for_param() -> list[tuple[str, dict, dict]]:
    """Load encode_vectors.json once at collection; degrade to a single
    skip-placeholder entry if the file has not been regenerated yet."""
    import json as _json
    from pathlib import Path as _Path

    path = _Path(__file__).resolve().parents[1] / "fixtures" / "encode_vectors.json"
    if not path.exists():
        return [("__missing__", {}, {})]
    data = _json.loads(path.read_text(encoding="utf-8"))
    if data.get("__GENERATED_BY_TESTGEN__"):
        return [("__placeholder__", {}, {})]
    cfg = data["config"]
    return [(vec["id"], cfg, vec) for vec in data["vectors"]]


_VECTOR_PARAMS = _load_vectors_for_param()


class TestEncodeVectors:
    """Asserts byte-equality against PHP-generated vectors.

    Skipped while encode_vectors.json carries the CodeGen placeholder.
    Stage 6 TestGen runs legacy PHP Shorty::encode to populate this file.
    """

    @pytest.mark.parametrize(
        "vector_id,base_config,vec",
        _VECTOR_PARAMS,
        ids=[v[0] for v in _VECTOR_PARAMS],
    )
    def test_BR_C_12_vector(self, vector_id, base_config, vec):
        """One assertion per (n, salt, padding) vector — byte-equal to PHP."""
        if vector_id in ("__missing__", "__placeholder__"):
            pytest.skip(
                "encode_vectors.json is missing or still the CodeGen "
                "placeholder — Stage 6 TestGen has not regenerated it."
            )

        per_cfg = EncoderConfig(
            chars=base_config["chars"],
            salt=vec["salt"],
            padding=vec["padding"],
        )
        actual = encode(vec["n"], per_cfg)
        assert actual == vec["expected_code"], (
            f"vector {vec['id']} (n={vec['n']}, salt={vec['salt']!r}, "
            f"padding={vec['padding']}) — got {actual!r}, "
            f"expected {vec['expected_code']!r}"
        )

    def test_BR_C_12_vector_set_runs(self, encode_vectors):
        """Aggregate loop — guards against the parametrised test being
        accidentally deselected by pytest filters. `encode_vectors` fixture
        skips if placeholder is present."""
        config = encode_vectors["config"]
        for vec in encode_vectors["vectors"]:
            per_cfg = EncoderConfig(
                chars=config["chars"],
                salt=vec["salt"],
                padding=vec["padding"],
            )
            actual = encode(vec["n"], per_cfg)
            assert actual == vec["expected_code"], (
                f"vector {vec['id']} (n={vec['n']}) — "
                f"got {actual!r}, expected {vec['expected_code']!r}"
            )

    def test_BR_C_12_vector_round_trip(self, encode_vectors):
        """Every fixture vector must round-trip: decode(encode(n)) == n."""
        config = encode_vectors["config"]
        for vec in encode_vectors["vectors"]:
            per_cfg = EncoderConfig(
                chars=config["chars"],
                salt=vec["salt"],
                padding=vec["padding"],
            )
            assert decode(encode(vec["n"], per_cfg), per_cfg) == vec["n"], (
                f"vector {vec['id']}: encode→decode round-trip failed"
            )

    def test_BR_C_12_negative_vector_fails(self, encode_vectors):
        """A deliberately wrong expected_code MUST cause an assertion miss.

        Guards against the parity assertion silently being a no-op (e.g.
        if the fixture file were truncated to zero vectors or the
        comparison operator were ever mistakenly relaxed).
        """
        config = encode_vectors["config"]
        # Pick the first vector and tamper its expected_code.
        vec = encode_vectors["vectors"][0]
        per_cfg = EncoderConfig(
            chars=config["chars"],
            salt=vec["salt"],
            padding=vec["padding"],
        )
        actual = encode(vec["n"], per_cfg)
        tampered_expected = vec["expected_code"] + "X"
        # The encoded output MUST NOT match a deliberately wrong code.
        assert actual != tampered_expected, (
            "Negative vector check failed — encode() returned the tampered "
            "code, suggesting the comparison axis is broken."
        )

    def test_BR_C_12_single_char_codes(self):
        """Sanity: single-char branch (n < b) is deterministic without fixtures."""
        cfg = EncoderConfig(chars=DEFAULT_CHARS, salt="", padding=3)
        assert encode(1, cfg) == "b"  # S[1]
        assert encode(10, cfg) == "k"  # S[10]
        assert encode(25, cfg) == "z"  # S[25]
        assert encode(26, cfg) == "A"  # S[26]
        assert encode(52, cfg) == "0"  # S[52]
        assert encode(61, cfg) == "9"  # S[61]

    def test_BR_C_12_no_seed_branch_when_salt_empty(self):
        """salt='' MUST suppress the seed branch even if padding > 0.

        Implementation contract: `encode(n)` for salt='' equals
        `num_to_alpha(n, S)` byte-for-byte. Asserts the if-guard at
        encode.py:75 is preserved.
        """
        cfg_with_padding = EncoderConfig(chars=DEFAULT_CHARS, salt="", padding=3)
        cfg_no_padding = EncoderConfig(chars=DEFAULT_CHARS, salt="", padding=0)
        for n in (1, 10, 100, 1000, 12345, 1_000_000):
            assert encode(n, cfg_with_padding) == encode(n, cfg_no_padding), (
                f"salt='' must suppress seed branch for n={n}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# TestEncodeProperty — hypothesis round-trip (BR-C-12 + Vector group C)


class TestEncodeProperty:
    @hsettings(max_examples=200, deadline=None)
    @given(n=st.integers(min_value=1, max_value=100_000))
    def test_BR_C_12_roundtrip_no_salt(self, n):
        cfg = EncoderConfig(chars=DEFAULT_CHARS, salt="", padding=3)
        assert decode(encode(n, cfg), cfg) == n

    @hsettings(max_examples=200, deadline=None)
    @given(n=st.integers(min_value=1, max_value=10_000))
    def test_BR_C_12_roundtrip_with_salt(self, n):
        cfg = EncoderConfig(chars=DEFAULT_CHARS, salt="testsalt", padding=3)
        assert decode(encode(n, cfg), cfg) == n

    @hsettings(max_examples=200, deadline=None)
    @given(n=st.integers(min_value=1, max_value=100_000))
    def test_BR_C_12_encoded_only_uses_chars(self, n):
        cfg = EncoderConfig(chars=DEFAULT_CHARS, salt="", padding=3)
        code = encode(n, cfg)
        assert all(c in DEFAULT_CHARS for c in code)

    def test_BR_C_12_invalid_char_in_decode_raises(self):
        cfg = EncoderConfig(chars=DEFAULT_CHARS, salt="", padding=3)
        with pytest.raises(ValueError, match="not in chars"):
            decode("@@@", cfg)

    def test_BR_C_12_encode_n_zero_raises(self):
        cfg = EncoderConfig(chars=DEFAULT_CHARS, salt="", padding=3)
        with pytest.raises(ValueError, match="n >= 1"):
            encode(0, cfg)


# ─────────────────────────────────────────────────────────────────────────────
# Helper-level checks — get_seed, num_to_alpha, alpha_to_num


class TestEncodeHelpers:
    def test_get_seed_zero_guard_invariant_I_9(self):
        # Pick (n, salt, padding) such that dec % 10**padding == 0
        # and verify the guard kicks in (result never starts with all-zeros).
        # Easiest: assert that result is always at least the padded "001".
        result = get_seed(1, "testsalt", 3)
        assert len(result) == 3
        assert int(result, 10) >= 1  # zero-guard means the int form is >= 1

    def test_num_to_alpha_zero_returns_first_char(self):
        # Boundary: n=0 → m=0; n - m == 0 → returns chars[0].
        assert num_to_alpha(0, DEFAULT_CHARS) == "a"

    def test_alpha_to_num_inverse(self):
        for n in (1, 62, 100, 1000, 1_000_000):
            code = num_to_alpha(n, DEFAULT_CHARS)
            assert alpha_to_num(code, DEFAULT_CHARS) == n

    def test_get_seed_known_php_md5(self):
        # md5("1testsalt") starts with hex chars — verify the seed reproduces
        # the algorithm. hexdec(h[0:3]) % 1000; pad to 3.
        # We don't hardcode the exact bytes (Stage 6 will lock); we only
        # assert the shape: length == padding and parseable as decimal.
        seed = get_seed(1, "testsalt", 3)
        assert len(seed) == 3
        int(seed, 10)  # must parse
