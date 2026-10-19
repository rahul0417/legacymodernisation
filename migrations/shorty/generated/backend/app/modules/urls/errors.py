# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-02, BR-C-04, BR-C-06, BR-C-12
# LEGACY: source/shorty.php:279-294 (not_found / error)
# COMPONENT: modules/urls/errors
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
Domain exception hierarchy for the urls module.

Service raises these; router catches them and maps to HTTP status codes
(see app/main.py exception handlers).

Replaces legacy PHP's `exit('<h1>Bad input.</h1>')` / `exit('<h1>404 Not
Found</h1>')` short-circuits with structured, testable exception objects
(RF-09 status-code uplift).
"""

from __future__ import annotations


class ShortyError(Exception):
    """Base class for all domain-specific errors."""

    detail: str = "Internal error"
    type_code: str = "shorty/internal"


class UrlNotFound(ShortyError):
    """Lookup by decoded id returned no row — BR-C-06.

    Also raised for malformed codes (post-strip non-alphanumeric) and for
    decode results that overflow INTEGER (OQ-C-03).
    """

    detail = "Not Found"
    type_code = "shorty/not-found"


class BadUrl(ShortyError):
    """Submitted URL failed the legacy regex (BR-C-02). Router maps → 400."""

    detail = "Bad input."
    type_code = "shorty/bad-input"


class StoredUrlCorrupt(ShortyError):
    """DB-loaded URL failed legacy-regex re-validation before redirect
    (RF-06 / OQ-C-02). Distinct from BadUrl because the failure indicates
    data-integrity corruption, not client error — router maps → 500 + ERROR log."""

    detail = "Internal error"
    type_code = "shorty/internal"


class IpNotAllowed(ShortyError):
    """Client IP not in non-empty SHORTY_IP_WHITELIST (BR-C-04)."""

    detail = "Not allowed."
    type_code = "shorty/not-allowed"


class EncodeOverflow(ShortyError):
    """Encode produced a value outside the configured alphabet — should
    only happen if the underlying integer arithmetic over/underflowed."""

    detail = "Internal error"
    type_code = "shorty/encode-overflow"
