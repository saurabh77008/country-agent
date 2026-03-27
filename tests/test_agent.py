"""Tests for the Country Information Agent."""

import pytest

from app.intent_parser import parse_intent, _extract_country, _extract_fields, _normalise
from app.synthesiser import synthesise_answer, _format_population
from app.models import CountryField


# ── Intent Parser Tests ───────────────────────────────────────────────────

class TestExtractCountry:
    def test_simple_country(self):
        assert _extract_country("what is the capital of france") is not None
        result = _extract_country("what is the capital of france")
        assert "france" in result.lower() or "France" in result

    def test_alias_usa(self):
        assert _extract_country("what is the population of usa") == "United States"

    def test_alias_uk(self):
        assert _extract_country("what currency does england use") == "United Kingdom"

    def test_no_country(self):
        result = _extract_country("what is the weather like")
        # May or may not find something — the key is it shouldn't crash
        assert result is None or isinstance(result, str)


class TestExtractFields:
    def test_capital(self):
        fields = _extract_fields("what is the capital of germany")
        assert CountryField.CAPITAL in fields

    def test_population(self):
        fields = _extract_fields("how many people live in brazil")
        assert CountryField.POPULATION in fields

    def test_currency(self):
        fields = _extract_fields("what currency does japan use")
        assert CountryField.CURRENCY in fields

    def test_multiple_fields(self):
        fields = _extract_fields("what is the capital and population of brazil")
        assert CountryField.CAPITAL in fields
        assert CountryField.POPULATION in fields

    def test_general_fallback(self):
        fields = _extract_fields("xyzabc")
        assert CountryField.GENERAL in fields


class TestParseIntent:
    def test_full_parse(self):
        result = parse_intent({"user_query": "What is the capital of France?"})
        assert result["country_name"] is not None
        assert CountryField.CAPITAL in result["requested_fields"]

    def test_error_on_no_country(self):
        result = parse_intent({"user_query": "hello"})
        # Should set an error or find no country
        assert result.get("error") or result.get("country_name") is None


# ── Synthesiser Tests ─────────────────────────────────────────────────────

class TestFormatPopulation:
    def test_billions(self):
        assert "billion" in _format_population(1_400_000_000)

    def test_millions(self):
        assert "million" in _format_population(83_000_000)

    def test_small(self):
        assert _format_population(50_000) == "50,000"

    def test_string_passthrough(self):
        assert _format_population("N/A") == "N/A"


class TestSynthesiseAnswer:
    def test_error_passthrough(self):
        result = synthesise_answer({"error": "something broke"})
        assert result["answer"] == "something broke"

    def test_single_field_capital(self):
        result = synthesise_answer({
            "country_name": "France",
            "requested_fields": [CountryField.CAPITAL],
            "extracted_data": {
                "capital": "Paris",
                "official_name": "French Republic",
            },
        })
        assert "Paris" in result["answer"]
        assert "France" in result["answer"]

    def test_general_query(self):
        result = synthesise_answer({
            "country_name": "Japan",
            "requested_fields": [CountryField.GENERAL],
            "extracted_data": {
                "capital": "Tokyo",
                "population": 125_800_000,
                "currency": "Japanese yen (JPY) — symbol: ¥",
                "official_name": "Japan",
            },
        })
        assert "Tokyo" in result["answer"]
        assert "125" in result["answer"]
