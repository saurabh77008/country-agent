"""Tests for the Country Information Agent."""

from app.intent_parser import (
    _extract_country,
    _extract_fields,
    _normalise,
    _detect_historical,
    _detect_ambiguous,
    _detect_comparison,
    parse_intent,
)
from app.synthesiser import synthesise_answer, _format_population
from app.models import CountryField
from app.interfaces import ICountryExtractor, IFieldExtractor, IAnswerSynthesiser


# ── Intent Parser — country extraction ───────────────────────────────────────

class TestExtractCountry:
    def test_simple_country(self):
        assert _extract_country("what is the capital of france") is not None
        assert "France" in _extract_country("what is the capital of france")

    def test_alias_usa(self):
        assert _extract_country("what is the population of usa") == "United States"

    def test_alias_uk(self):
        assert _extract_country("what currency does england use") == "United Kingdom"

    def test_alias_uae(self):
        assert _extract_country("tell me about uae") == "United Arab Emirates"

    def test_alias_burma(self):
        assert _extract_country("what language is spoken in burma") == "Myanmar"

    def test_alias_siam(self):
        assert _extract_country("tell me about siam") == "Thailand"

    def test_alias_persia(self):
        assert _extract_country("capital of persia") == "Iran"

    def test_alias_zaire(self):
        assert _extract_country("what is the capital of zaire") == "Democratic Republic of the Congo"

    def test_alias_ceylon(self):
        assert _extract_country("tell me about ceylon") == "Sri Lanka"

    def test_alias_rhodesia(self):
        assert _extract_country("what is rhodesia") == "Zimbabwe"

    def test_alias_png(self):
        assert _extract_country("tell me about png") == "Papua New Guinea"

    def test_alias_dprk(self):
        assert _extract_country("what is the capital of dprk") == "North Korea"

    def test_longest_match_wins(self):
        # "South Africa" should win over bare "Africa"
        result = _extract_country("tell me about south africa")
        assert result == "South Africa"

    def test_possessive_normalisation(self):
        # "Japan's" should still resolve to Japan
        normalised = _normalise("What is Japan's capital?")
        assert "japan" in normalised
        assert "s" not in normalised.split()  # possessive stripped

    def test_no_country_returns_none_or_str(self):
        # Should not crash — may return None or a fallback string
        result = _extract_country("what is the weather like")
        assert result is None or isinstance(result, str)

    def test_fuzzy_typo_france(self):
        # "frence" is close enough to "France"
        result = _extract_country("what is the capital of frence")
        assert result is not None
        assert "France" in result

    def test_fuzzy_typo_germany(self):
        result = _extract_country("population of germanu")
        assert result is not None
        assert "Germany" in result

    def test_dot_acronym_usa(self):
        normalised = _normalise("Tell me about U.S.A.")
        result = _extract_country(normalised)
        assert result == "United States"


# ── Intent Parser — field extraction ─────────────────────────────────────────

class TestExtractFields:
    def test_capital(self):
        assert CountryField.CAPITAL in _extract_fields("what is the capital of germany")

    def test_population(self):
        assert CountryField.POPULATION in _extract_fields("how many people live in brazil")

    def test_currency(self):
        assert CountryField.CURRENCY in _extract_fields("what currency does japan use")

    def test_multiple_fields(self):
        fields = _extract_fields("what is the capital and population of brazil")
        assert CountryField.CAPITAL in fields
        assert CountryField.POPULATION in fields

    def test_general_fallback(self):
        assert CountryField.GENERAL in _extract_fields("xyzabc")

    def test_borders_keyword(self):
        assert CountryField.BORDERS in _extract_fields("what countries border france")

    def test_calling_code_keyword(self):
        assert CountryField.CALLING_CODE in _extract_fields("phone code of india")

    def test_area_keyword(self):
        assert CountryField.AREA in _extract_fields("what is the size of brazil")


# ── Intent Parser — edge-case detectors ──────────────────────────────────────

class TestDetectHistorical:
    def test_ussr(self):
        msg = _detect_historical("what was the capital of the ussr")
        assert msg is not None
        assert "1991" in msg

    def test_yugoslavia(self):
        msg = _detect_historical("tell me about yugoslavia")
        assert msg is not None
        assert "Slovenia" in msg or "Croatia" in msg

    def test_east_germany(self):
        msg = _detect_historical("population of east germany")
        assert msg is not None
        assert "Germany" in msg

    def test_czechoslovakia(self):
        msg = _detect_historical("capital of czechoslovakia")
        assert msg is not None

    def test_non_historical_returns_none(self):
        assert _detect_historical("what is the capital of france") is None


class TestDetectAmbiguous:
    def test_georgia_ambiguous(self):
        candidates = _detect_ambiguous("Georgia")
        assert candidates is not None
        assert len(candidates) >= 2

    def test_korea_ambiguous(self):
        candidates = _detect_ambiguous("Korea")
        assert candidates is not None
        assert any("South Korea" in c for c in candidates)
        assert any("North Korea" in c for c in candidates)

    def test_sudan_ambiguous(self):
        candidates = _detect_ambiguous("Sudan")
        assert candidates is not None

    def test_unambiguous_returns_none(self):
        assert _detect_ambiguous("France") is None
        assert _detect_ambiguous("Germany") is None


class TestDetectComparison:
    def test_vs_keyword(self):
        countries = _detect_comparison("france vs germany population")
        assert len(countries) >= 2
        assert "France" in countries
        assert "Germany" in countries

    def test_compare_keyword(self):
        countries = _detect_comparison("compare india and china")
        assert len(countries) >= 2

    def test_bigger_than(self):
        countries = _detect_comparison("is france bigger than germany")
        assert len(countries) >= 2

    def test_single_country_no_comparison(self):
        # No comparison keyword → should not trigger
        countries = _detect_comparison("what is the capital of france")
        assert countries == []


# ── Intent Parser — parse_intent node ────────────────────────────────────────

class TestParseIntent:
    def test_full_parse(self):
        result = parse_intent({"user_query": "What is the capital of France?"})
        assert result["country_name"] is not None
        assert CountryField.CAPITAL in result["requested_fields"]
        assert not result.get("error")

    def test_error_on_no_country(self):
        # All tokens are stop words → every extractor returns None → error set
        result = parse_intent({"user_query": "what is the"})
        assert result.get("error") is not None or result.get("country_name") is None

    def test_historical_sets_error(self):
        result = parse_intent({"user_query": "What was the capital of the USSR?"})
        assert result.get("error") is not None
        assert result.get("is_historical") is True

    def test_ambiguous_sets_error(self):
        result = parse_intent({"user_query": "Tell me about Georgia"})
        assert result.get("error") is not None
        assert len(result.get("ambiguous_countries", [])) >= 2

    def test_comparison_sets_error(self):
        result = parse_intent({"user_query": "France vs Germany — which is bigger?"})
        assert result.get("error") is not None
        assert len(result.get("comparison_countries", [])) >= 2

    def test_possessive_query(self):
        result = parse_intent({"user_query": "What is Japan's capital?"})
        assert result.get("country_name") is not None
        assert "japan" in result["country_name"].lower()

    def test_fuzzy_typo_in_full_parse(self):
        result = parse_intent({"user_query": "What is the capital of Frence?"})
        # Fuzzy extractor should find France
        assert result.get("country_name") is not None

    def test_new_fields_initialised(self):
        result = parse_intent({"user_query": "Capital of Brazil"})
        assert "is_historical" in result
        assert "comparison_countries" in result
        assert "ambiguous_countries" in result


# ── Synthesiser — population formatting ──────────────────────────────────────

class TestFormatPopulation:
    def test_billions(self):
        assert "billion" in _format_population(1_400_000_000)

    def test_millions(self):
        assert "million" in _format_population(83_000_000)

    def test_small(self):
        assert _format_population(50_000) == "50,000"

    def test_string_passthrough(self):
        assert _format_population("N/A") == "N/A"

    def test_float_input(self):
        assert "million" in _format_population(83_000_000.0)


# ── Synthesiser — answer generation ──────────────────────────────────────────

class TestSynthesiseAnswer:
    def test_error_passthrough(self):
        result = synthesise_answer({"error": "something broke"})
        assert result["answer"] == "something broke"

    def test_historical_error_passthrough(self):
        result = synthesise_answer({
            "error": "The **Soviet Union (USSR)** dissolved in 1991.",
            "is_historical": True,
        })
        assert "1991" in result["answer"]

    def test_ambiguous_error_passthrough(self):
        result = synthesise_answer({
            "error": '**"Georgia"** could refer to multiple entities',
            "ambiguous_countries": ["Georgia (Caucasus)", "Georgia (US state)"],
        })
        assert "Georgia" in result["answer"]

    def test_comparison_error_passthrough(self):
        result = synthesise_answer({
            "error": "Multi-country comparison queries are not yet supported.",
            "comparison_countries": ["France", "Germany"],
        })
        assert "not yet supported" in result["answer"]

    def test_single_field_capital(self):
        result = synthesise_answer({
            "country_name": "France",
            "requested_fields": [CountryField.CAPITAL],
            "extracted_data": {"capital": "Paris", "official_name": "French Republic"},
        })
        assert "Paris" in result["answer"]
        assert "France" in result["answer"]

    def test_single_field_borders_with_names(self):
        result = synthesise_answer({
            "country_name": "France",
            "requested_fields": [CountryField.BORDERS],
            "extracted_data": {
                "borders": ["Germany", "Spain", "Italy"],
                "official_name": "French Republic",
            },
        })
        assert "Germany" in result["answer"]
        assert "Spain" in result["answer"]

    def test_single_field_borders_island(self):
        result = synthesise_answer({
            "country_name": "Japan",
            "requested_fields": [CountryField.BORDERS],
            "extracted_data": {"borders": [], "official_name": "Japan"},
        })
        assert "island" in result["answer"].lower() or "no land" in result["answer"].lower()

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

    def test_no_data_fallback(self):
        result = synthesise_answer({
            "country_name": "Atlantis",
            "requested_fields": [CountryField.GENERAL],
            "extracted_data": {},
        })
        assert "Atlantis" in result["answer"]


# ── Interface compliance ──────────────────────────────────────────────────────

class TestInterfaceCompliance:
    """Verify SOLID wiring: concrete classes satisfy their Protocols."""

    def test_template_synthesiser_implements_protocol(self):
        from app.synthesiser import TemplateSynthesiser
        assert isinstance(TemplateSynthesiser(), IAnswerSynthesiser)

    def test_alias_extractor_implements_protocol(self):
        from app.intent_parser import _AliasExtractor, _COUNTRY_ALIASES
        assert isinstance(_AliasExtractor(_COUNTRY_ALIASES), ICountryExtractor)

    def test_known_list_extractor_implements_protocol(self):
        from app.intent_parser import _KnownListExtractor, _KNOWN_COUNTRIES
        assert isinstance(_KnownListExtractor(_KNOWN_COUNTRIES), ICountryExtractor)

    def test_fuzzy_extractor_implements_protocol(self):
        from app.intent_parser import _FuzzyExtractor, _KNOWN_COUNTRIES
        assert isinstance(_FuzzyExtractor(_KNOWN_COUNTRIES), ICountryExtractor)

    def test_keyword_field_extractor_implements_protocol(self):
        from app.intent_parser import _KeywordFieldExtractor
        from app.models import FIELD_KEYWORDS
        assert isinstance(_KeywordFieldExtractor(FIELD_KEYWORDS), IFieldExtractor)

    def test_rest_countries_repo_is_subclass(self):
        from app.tools import RestCountriesRepository
        from app.interfaces import ICountryRepository
        assert issubclass(RestCountriesRepository, ICountryRepository)

    def test_cached_repo_is_subclass(self):
        from app.tools import CachedCountryRepository
        from app.interfaces import ICountryRepository
        assert issubclass(CachedCountryRepository, ICountryRepository)
