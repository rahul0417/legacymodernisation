# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-01, BR-C-05, BR-C-07, BR-C-09, BR-C-12
# LEGACY: source/shorty.php (entire surface)
# COMPONENT: tests/parity/test_php_parity
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
Dual-run parity scaffold — Stage 7 wires this up against the live PHP
reference container (docker compose --profile parity up).

All tests skip unless the env vars `PHP_REFERENCE_URL` and
`PYTHON_TARGET_URL` are set. Stage 7 fills in:
  - Volatile-header strip (Date, Server, Content-Length, X-Powered-By).
  - Body normalisation per Planning §12.2.
  - Status-code uplift map (PHP 200 → FastAPI 400/403/404).
  - ~55-input matrix from Planning §12.1.
"""

from __future__ import annotations

import os

import pytest

pytestmark = [pytest.mark.parity]


_PHP_URL = os.environ.get("PHP_REFERENCE_URL")
_PY_URL = os.environ.get("PYTHON_TARGET_URL")
_BOTH_CONFIGURED = bool(_PHP_URL and _PY_URL)


@pytest.mark.skipif(not _BOTH_CONFIGURED, reason="PHP_REFERENCE_URL/PYTHON_TARGET_URL not set")
class TestPhpParity:
    def test_create_text_body_matches(self):
        """Stage 7 fills in: GET both targets and diff after header strip."""
        pytest.skip("Stage 7 will populate the diff harness.")

    def test_create_xml_body_byte_for_byte(self):
        pytest.skip("Stage 7 will populate the diff harness.")

    def test_encode_vector_roundtrip_matches_php(self):
        pytest.skip("Stage 7 will populate the diff harness.")

    def test_lookup_redirect_location_matches(self):
        pytest.skip("Stage 7 will populate the diff harness.")
