"""
Node 1 — Intent & Field Identification

Extracts country name + requested fields from a user query.
Uses a known country list with longest-match-first strategy.
"""

import re
from typing import Dict, List, Optional

from app.models import CountryField, FIELD_KEYWORDS

# ── Known countries ───────────────────────────────────────────────────────

_KNOWN_COUNTRIES: List[str] = [
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda",
    "Argentina", "Armenia", "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain",
    "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bhutan",
    "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria",
    "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia", "Cameroon", "Canada",
    "Central African Republic", "Chad", "Chile", "China", "Colombia", "Comoros",
    "Congo", "Costa Rica", "Croatia", "Cuba", "Cyprus", "Czechia", "Denmark",
    "Djibouti", "Dominica", "Dominican Republic", "Ecuador", "Egypt", "El Salvador",
    "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji",
    "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany", "Ghana", "Greece",
    "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti", "Honduras",
    "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel",
    "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati",
    "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia",
    "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar", "Malawi",
    "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania",
    "Mauritius", "Mexico", "Micronesia", "Moldova", "Monaco", "Mongolia",
    "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia", "Nauru", "Nepal",
    "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea",
    "North Macedonia", "Norway", "Oman", "Pakistan", "Palau", "Palestine", "Panama",
    "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland", "Portugal",
    "Qatar", "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia",
    "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe",
    "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore",
    "Slovakia", "Slovenia", "Solomon Islands", "Somalia", "South Africa", "South Korea",
    "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland",
    "Syria", "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo",
    "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan", "Tuvalu",
    "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "United States",
    "Uruguay", "Uzbekistan", "Vanuatu", "Vatican City", "Venezuela", "Vietnam",
    "Yemen", "Zambia", "Zimbabwe",
]

_COUNTRY_LOOKUP: Dict[str, str] = {c.lower(): c for c in _KNOWN_COUNTRIES}

_COUNTRY_ALIASES: Dict[str, str] = {
    "usa": "United States",
    "us": "United States",
    "u.s.": "United States",
    "u.s.a.": "United States",
    "america": "United States",
    "united states of america": "United States",
    "the united states": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "england": "United Kingdom",
    "britain": "United Kingdom",
    "great britain": "United Kingdom",
    "uae": "United Arab Emirates",
    "emirates": "United Arab Emirates",
    "holland": "Netherlands",
    "the netherlands": "Netherlands",
    "czech republic": "Czechia",
    "ivory coast": "Cote d'Ivoire",
    "burma": "Myanmar",
    "persia": "Iran",
    "brasil": "Brazil",
    "deutschland": "Germany",
    "nippon": "Japan",
    "nihon": "Japan",
    "south korea": "South Korea",
    "north korea": "North Korea",
    "vatican": "Vatican City",
    "the philippines": "Philippines",
    "drc": "Congo",
    "dr congo": "Congo",
    "bosnia": "Bosnia and Herzegovina",
}


def _normalise(text: str) -> str:
    return re.sub(r"[^\w\s']", " ", text.lower()).strip()


def _extract_country(query_lower: str) -> Optional[str]:
    """Extract country name using alias table + known country list."""

    # 1. Aliases first (longest match wins)
    for alias, canonical in sorted(_COUNTRY_ALIASES.items(), key=lambda x: -len(x[0])):
        if len(alias) <= 3:
            if re.search(r'\b' + re.escape(alias) + r'\b', query_lower):
                return canonical
        else:
            if alias in query_lower:
                return canonical

    # 2. Known countries (longest first so "South Africa" beats "Africa"-substring)
    for country_lower, country_proper in sorted(_COUNTRY_LOOKUP.items(), key=lambda x: -len(x[0])):
        if country_lower in query_lower:
            return country_proper

    # 3. Fallback: strip keywords/stopwords, use whatever remains
    cleaned = query_lower
    for kw in sorted(FIELD_KEYWORDS.keys(), key=len, reverse=True):
        cleaned = cleaned.replace(kw, " ")

    _stop = frozenset(
        "what is the of in a an and for does do how many which tell me about "
        "can you give show please could would who where when why has have with "
        "its their people live use used to it that this are be been being "
        "country nation state land".split()
    )
    tokens = cleaned.split()
    candidates = [t for t in tokens if t not in _stop and len(t) > 1]
    if candidates:
        return " ".join(candidates).title()

    return None


def _extract_fields(query_lower: str) -> List[CountryField]:
    found: List[CountryField] = []
    for keyword, field in sorted(FIELD_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if keyword in query_lower and field not in found:
            found.append(field)
    if not found:
        found.append(CountryField.GENERAL)
    return found


def parse_intent(state: dict) -> dict:
    """LangGraph node — parse user intent."""
    query = state.get("user_query", "")
    normalised = _normalise(query)

    country = _extract_country(normalised)
    fields = _extract_fields(normalised)

    updates: dict = {
        "country_name": country,
        "requested_fields": fields,
    }

    if not country:
        updates["error"] = (
            "I couldn't identify a country in your question. "
            "Could you rephrase it? For example: \"What is the capital of France?\""
        )

    return updates
