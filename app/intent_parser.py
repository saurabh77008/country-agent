"""
Node 1 — Intent & Field Identification

Extracts country name + requested fields from a user query.

SOLID design:
  SRP — each extractor class does exactly one thing
  OCP — add new extraction strategies by adding a class, not editing existing ones
  LSP — all extractors are interchangeable via ICountryExtractor
  DIP — parse_intent depends on ICountryExtractor / IFieldExtractor abstractions

Edge cases handled:
  • Possessive forms          "Japan's capital"  → "Japan"
  • Common aliases            "USA", "UAE", "Burma", "Siam", "Persia" …
  • Fuzzy / typo matching     "Frence" → France,  "Germanu" → Germany
  • Ambiguous names           "Georgia", "Korea", "Sudan", "Congo", "Guinea"
  • Historical / defunct      "USSR", "Yugoslavia", "East Germany" …
  • Multi-country comparison  "France vs Germany", "compare India and China"
  • Dot-separated acronyms    "U.S.A." → "usa"
"""

from __future__ import annotations

import difflib
import re
from typing import Dict, List, Optional

from app.interfaces import ICountryExtractor, IFieldExtractor
from app.models import (
    AMBIGUOUS_COUNTRIES,
    HISTORICAL_COUNTRIES,
    CountryField,
    FIELD_KEYWORDS,
)

# ── Data ──────────────────────────────────────────────────────────────────────

_KNOWN_COUNTRIES: List[str] = [
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola",
    "Antigua and Barbuda", "Argentina", "Armenia", "Australia", "Austria",
    "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus",
    "Belgium", "Belize", "Benin", "Bhutan", "Bolivia",
    "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria",
    "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia", "Cameroon",
    "Canada", "Central African Republic", "Chad", "Chile", "China",
    "Colombia", "Comoros", "Congo", "Costa Rica", "Croatia", "Cuba",
    "Cyprus", "Czechia", "Denmark", "Djibouti", "Dominica",
    "Dominican Republic", "Ecuador", "Egypt", "El Salvador",
    "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia",
    "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany",
    "Ghana", "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau",
    "Guyana", "Haiti", "Honduras", "Hungary", "Iceland", "India",
    "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy", "Jamaica",
    "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Kuwait",
    "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia",
    "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar",
    "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands",
    "Mauritania", "Mauritius", "Mexico", "Micronesia", "Moldova", "Monaco",
    "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia",
    "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger",
    "Nigeria", "North Korea", "North Macedonia", "Norway", "Oman",
    "Pakistan", "Palau", "Palestine", "Panama", "Papua New Guinea",
    "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar",
    "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia",
    "Saint Vincent and the Grenadines", "Samoa", "San Marino",
    "Sao Tome and Principe", "Saudi Arabia", "Senegal", "Serbia",
    "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia",
    "Solomon Islands", "Somalia", "South Africa", "South Korea",
    "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden",
    "Switzerland", "Syria", "Taiwan", "Tajikistan", "Tanzania", "Thailand",
    "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago", "Tunisia",
    "Turkey", "Turkmenistan", "Tuvalu", "Uganda", "Ukraine",
    "United Arab Emirates", "United Kingdom", "United States", "Uruguay",
    "Uzbekistan", "Vanuatu", "Vatican City", "Venezuela", "Vietnam",
    "Yemen", "Zambia", "Zimbabwe",
]

_COUNTRY_LOOKUP: Dict[str, str] = {c.lower(): c for c in _KNOWN_COUNTRIES}

# OCP: extend this dict to add aliases; never modify extractor logic
_COUNTRY_ALIASES: Dict[str, str] = {
    # United States
    "usa": "United States",
    "us": "United States",
    "u.s.": "United States",
    "u.s.a.": "United States",
    "america": "United States",
    "united states of america": "United States",
    "the united states": "United States",
    # United Kingdom
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "england": "United Kingdom",
    "britain": "United Kingdom",
    "great britain": "United Kingdom",
    # UAE
    "uae": "United Arab Emirates",
    "u.a.e.": "United Arab Emirates",
    "emirates": "United Arab Emirates",
    # Europe
    "holland": "Netherlands",
    "the netherlands": "Netherlands",
    "czech republic": "Czechia",
    "deutschland": "Germany",
    # Asia
    "nippon": "Japan",
    "nihon": "Japan",
    "burma": "Myanmar",
    "persia": "Iran",
    "siam": "Thailand",
    "south korea": "South Korea",
    "north korea": "North Korea",
    "dprk": "North Korea",
    "rok": "South Korea",
    "formosa": "Taiwan",
    "timor": "Timor-Leste",
    # Africa
    "ivory coast": "Cote d'Ivoire",
    "drc": "Democratic Republic of the Congo",
    "dr congo": "Democratic Republic of the Congo",
    "zaire": "Democratic Republic of the Congo",
    "rhodesia": "Zimbabwe",
    "ceylon": "Sri Lanka",
    # Americas
    "brasil": "Brazil",
    # Pacific
    "png": "Papua New Guinea",
    # Other
    "vatican": "Vatican City",
    "the philippines": "Philippines",
    "bosnia": "Bosnia and Herzegovina",
    "trinidad": "Trinidad and Tobago",
    "saint kitts": "Saint Kitts and Nevis",
    "st kitts": "Saint Kitts and Nevis",
    "saint lucia": "Saint Lucia",
    "st lucia": "Saint Lucia",
    "saint vincent": "Saint Vincent and the Grenadines",
    "st vincent": "Saint Vincent and the Grenadines",
}

# Regex that detects multi-country comparison intent
_COMPARISON_RE = re.compile(
    r"\b(vs\.?|versus|compare(?:d)?(?:\s+to)?|bigger than|larger than|"
    r"smaller than|difference between|between .+ and|more than|less than)\b",
    re.IGNORECASE,
)

_STOP_WORDS = frozenset(
    "what is the of in a an and for does do how many which tell me about "
    "can you give show please could would who where when why has have with "
    "its their people live use used to it that this are be been being "
    "country nation state land".split()
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    """Lower-case, remove punctuation, expand possessives, collapse spaces."""
    # Remove possessives before stripping punctuation so "japan's" → "japan"
    text = re.sub(r"'s\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"s'\b", "", text, flags=re.IGNORECASE)
    # Remove dots in acronyms so "U.S.A." → "usa"
    text = re.sub(r"(?<=[a-zA-Z])\.(?=[a-zA-Z])", "", text)
    # Strip remaining non-word chars (keep spaces)
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


# ── Extractor classes (SRP + OCP + LSP) ──────────────────────────────────────

class _AliasExtractor:
    """
    Checks a static alias dictionary.
    OCP: extend by adding entries to _COUNTRY_ALIASES — never edit this class.
    """

    def __init__(self, aliases: Dict[str, str]) -> None:
        # Sort longest-first so "united states of america" wins over "america"
        self._aliases = sorted(aliases.items(), key=lambda x: -len(x[0]))

    def extract(self, text: str) -> str | None:
        for alias, canonical in self._aliases:
            if len(alias) <= 3:
                # Short aliases need word-boundary protection to avoid
                # "us" matching inside "thus", "plus", etc.
                if re.search(r"\b" + re.escape(alias) + r"\b", text):
                    return canonical
            else:
                if alias in text:
                    return canonical
        return None


class _KnownListExtractor:
    """
    Exact substring match against the canonical country list.
    Tries longest names first so "South Africa" beats a bare "Africa".
    """

    def __init__(self, countries: List[str]) -> None:
        self._lookup: Dict[str, str] = {c.lower(): c for c in countries}
        self._sorted = sorted(self._lookup.items(), key=lambda x: -len(x[0]))

    def extract(self, text: str) -> str | None:
        for country_lower, country_proper in self._sorted:
            if country_lower in text:
                return country_proper
        return None


class _FuzzyExtractor:
    """
    Fuzzy match using difflib against the known countries list.
    Handles typos like "Frence" → France, "Germanu" → Germany.
    OCP: swap difflib for another library by subclassing — callers unchanged.
    """

    def __init__(self, countries: List[str], cutoff: float = 0.82) -> None:
        self._countries_lower = {c.lower(): c for c in countries}
        self._cutoff = cutoff

    def extract(self, text: str) -> str | None:
        words = text.split()
        # Try trigrams → bigrams → unigrams (longest candidate first)
        for n in range(min(3, len(words)), 0, -1):
            for i in range(len(words) - n + 1):
                phrase = " ".join(words[i : i + n])
                if len(phrase) < 4:
                    # Skip very short phrases to avoid false positives
                    continue
                matches = difflib.get_close_matches(
                    phrase,
                    self._countries_lower.keys(),
                    n=1,
                    cutoff=self._cutoff,
                )
                if matches:
                    return self._countries_lower[matches[0]]
        return None


class _FallbackExtractor:
    """
    Last-resort: strips field keywords and stop-words; returns whatever remains.
    This intentionally has a high false-positive rate — it only runs when all
    other extractors have already failed.
    """

    def extract(self, text: str) -> str | None:
        cleaned = text
        for kw in sorted(FIELD_KEYWORDS.keys(), key=len, reverse=True):
            cleaned = cleaned.replace(kw, " ")
        tokens = [t for t in cleaned.split() if t not in _STOP_WORDS and len(t) > 1]
        if tokens:
            return " ".join(tokens).title()
        return None


class _CompositeCountryExtractor:
    """
    Chain of responsibility: tries extractors in priority order, returns the
    first non-None result.
    OCP: inject a different list of extractors without touching callers.
    DIP: depends on the ICountryExtractor Protocol, not concrete classes.
    """

    def __init__(self, extractors: list) -> None:
        self._extractors = extractors

    def extract(self, text: str) -> str | None:
        for extractor in self._extractors:
            result = extractor.extract(text)
            if result:
                return result
        return None


class _KeywordFieldExtractor:
    """
    Maps FIELD_KEYWORDS to CountryField enum values.
    SRP: only responsible for field detection, nothing else.
    """

    def __init__(self, keywords: Dict[str, CountryField]) -> None:
        self._keywords = sorted(keywords.items(), key=lambda x: -len(x[0]))

    def extract(self, text: str) -> List[CountryField]:
        found: List[CountryField] = []
        for keyword, field in self._keywords:
            if keyword in text and field not in found:
                found.append(field)
        if not found:
            found.append(CountryField.GENERAL)
        return found


# ── Module-level singletons (DIP: nodes depend on abstractions) ───────────────

_country_extractor: ICountryExtractor = _CompositeCountryExtractor(
    [
        _AliasExtractor(_COUNTRY_ALIASES),
        _KnownListExtractor(_KNOWN_COUNTRIES),
        _FuzzyExtractor(_KNOWN_COUNTRIES),
        _FallbackExtractor(),
    ]
)

_field_extractor: IFieldExtractor = _KeywordFieldExtractor(FIELD_KEYWORDS)


# ── Edge-case detectors ───────────────────────────────────────────────────────

def _detect_historical(query_lower: str) -> Optional[str]:
    """Return the historical-country message if the query names a defunct state."""
    for name, message in HISTORICAL_COUNTRIES.items():
        if name in query_lower:
            return message
    return None


def _detect_ambiguous(country: str) -> Optional[List[str]]:
    """Return candidate list if the country name is ambiguous."""
    return AMBIGUOUS_COUNTRIES.get(country.lower())


def _detect_comparison(query_lower: str) -> List[str]:
    """
    Return the two (or more) countries if this looks like a comparison query.
    Only fires when an explicit comparison keyword is present.
    """
    if not _COMPARISON_RE.search(query_lower):
        return []

    # Collect all countries mentioned in the query
    found: List[str] = []
    for country_lower, country_proper in sorted(
        _COUNTRY_LOOKUP.items(), key=lambda x: -len(x[0])
    ):
        if country_lower in query_lower and country_proper not in found:
            found.append(country_proper)

    # Also check aliases
    for alias, canonical in sorted(_COUNTRY_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in query_lower and canonical not in found:
            found.append(canonical)

    return found if len(found) >= 2 else []


# ── Public helpers (kept for backward-compat with existing tests) ─────────────

def _extract_country(query_lower: str) -> Optional[str]:
    """Kept for test backward-compatibility. Delegates to the composite extractor."""
    return _country_extractor.extract(query_lower)


def _extract_fields(query_lower: str) -> List[CountryField]:
    """Kept for test backward-compatibility. Delegates to the keyword extractor."""
    return _field_extractor.extract(query_lower)


# ── LangGraph node ────────────────────────────────────────────────────────────

def parse_intent(state: dict) -> dict:
    """
    LangGraph node — parse user intent.

    Sets in the returned dict:
      country_name        — canonical country name (or None)
      requested_fields    — list of CountryField values
      error               — human-readable error / clarification (or None)
      is_historical       — True when the query is about a defunct country
      comparison_countries— list of countries when a comparison is detected
      ambiguous_countries — candidate list when the name is ambiguous
    """
    query = state.get("user_query", "")
    normalised = _normalise(query)

    updates: dict = {
        "is_historical": False,
        "comparison_countries": [],
        "ambiguous_countries": [],
    }

    # ── 1. Historical country check (before extraction, highest priority) ──
    historical_msg = _detect_historical(normalised)
    if historical_msg:
        updates["error"] = historical_msg
        updates["is_historical"] = True
        updates["requested_fields"] = [CountryField.GENERAL]
        return updates

    # ── 2. Comparison / multi-country check ───────────────────────────────
    comparison = _detect_comparison(normalised)
    if comparison:
        updates["comparison_countries"] = comparison
        updates["error"] = (
            f"Multi-country comparison queries are not yet supported. "
            f"I detected: **{', '.join(comparison)}**. "
            f"Try asking about each country individually."
        )
        updates["requested_fields"] = [CountryField.GENERAL]
        return updates

    # ── 3. Extract country and fields ─────────────────────────────────────
    country = _country_extractor.extract(normalised)
    fields = _field_extractor.extract(normalised)

    updates["country_name"] = country
    updates["requested_fields"] = fields

    if not country:
        updates["error"] = (
            "I couldn't identify a country in your question. "
            "Could you rephrase it? For example: \"What is the capital of France?\""
        )
        return updates

    # ── 4. Ambiguous country check ────────────────────────────────────────
    candidates = _detect_ambiguous(country)
    if candidates:
        updates["ambiguous_countries"] = candidates
        updates["error"] = (
            f'**"{country}"** could refer to multiple entities: '
            + ", ".join(f"**{c}**" for c in candidates)
            + ". Please be more specific in your question."
        )
        return updates

    return updates
