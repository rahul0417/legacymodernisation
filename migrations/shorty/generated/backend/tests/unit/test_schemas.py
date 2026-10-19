# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-02, BR-C-09
# LEGACY: source/shorty.php:332
# COMPONENT: tests/unit/test_schemas
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""Unit tests for Pydantic schemas (BR-C-02 regex parity, BR-C-09 format parse)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.urls.schemas import (
    CreateUrlRequest,
    OutputFormat,
    ProblemDetail,
)


class TestCreateUrlRequest:
    def test_BR_C_02_valid_http_url_accepted(self):
        req = CreateUrlRequest(url="http://example.com")
        assert req.url == "http://example.com"

    def test_BR_C_02_valid_https_url_accepted(self):
        req = CreateUrlRequest(url="https://example.com/path?x=1")
        assert req.url.startswith("https://")

    def test_BR_C_02_single_char_hostname_accepted(self):
        # "http://a" — `\w+` matches a single char.
        CreateUrlRequest(url="http://a")

    def test_BR_C_02_ipv4_accepted_regex_not_end_anchored(self):
        # The legacy regex `^http[s]?://\w+` is NOT end-anchored.
        # `\w+` only needs to match the first hostname segment ("192");
        # the trailing `.168.1.1` is not validated. Both PHP and the Python
        # target accept this. Corrects Discovery/Comprehension BR-02 wording.
        req = CreateUrlRequest(url="http://192.168.1.1")
        assert req.url == "http://192.168.1.1"

    def test_BR_C_02_uppercase_scheme_rejected(self):
        # Regex is case-sensitive on scheme.
        with pytest.raises(ValidationError):
            CreateUrlRequest(url="HTTP://example.com")

    def test_BR_C_02_ftp_rejected(self):
        with pytest.raises(ValidationError):
            CreateUrlRequest(url="ftp://example.com")

    def test_BR_C_02_empty_rejected(self):
        with pytest.raises(ValidationError):
            CreateUrlRequest(url="")

    def test_BR_C_02_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            CreateUrlRequest(url="http://example.com", malicious="x")


class TestOutputFormatParse:
    def test_BR_C_09_text(self):
        assert OutputFormat.parse("text") is OutputFormat.TEXT

    def test_BR_C_09_json(self):
        assert OutputFormat.parse("json") is OutputFormat.JSON

    def test_BR_C_09_xml(self):
        assert OutputFormat.parse("xml") is OutputFormat.XML

    def test_BR_C_09_html_explicit(self):
        assert OutputFormat.parse("html") is OutputFormat.HTML

    def test_BR_C_09_uppercase_text(self):
        # Case-insensitive parse.
        assert OutputFormat.parse("TEXT") is OutputFormat.TEXT

    def test_BR_C_09_mixed_case_json(self):
        assert OutputFormat.parse("Json") is OutputFormat.JSON

    def test_BR_C_09_unknown_defaults_html(self):
        assert OutputFormat.parse("yaml") is OutputFormat.HTML

    def test_BR_C_09_none_defaults_html(self):
        assert OutputFormat.parse(None) is OutputFormat.HTML

    def test_BR_C_09_empty_string_defaults_html(self):
        assert OutputFormat.parse("") is OutputFormat.HTML


class TestProblemDetail:
    def test_minimal_detail(self):
        pd = ProblemDetail(detail="x")
        assert pd.detail == "x"
        assert pd.type is None

    def test_extra_ignored(self):
        # extra="ignore" — unknown fields silently dropped.
        pd = ProblemDetail.model_validate({"detail": "x", "noise": 1})
        assert pd.detail == "x"
