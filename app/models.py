"""Pydantic models and shared domain data for the Country Information Agent."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CountryField(str, Enum):
    CAPITAL = "capital"
    POPULATION = "population"
    CURRENCY = "currency"
    LANGUAGE = "language"
    REGION = "region"
    SUBREGION = "subregion"
    FLAG = "flag"
    AREA = "area"
    TIMEZONE = "timezone"
    BORDERS = "borders"
    CONTINENT = "continent"
    CALLING_CODE = "calling_code"
    GENERAL = "general"


FIELD_KEYWORDS: Dict[str, CountryField] = {
    "capital": CountryField.CAPITAL,
    "population": CountryField.POPULATION,
    "people": CountryField.POPULATION,
    "inhabitants": CountryField.POPULATION,
    "currency": CountryField.CURRENCY,
    "money": CountryField.CURRENCY,
    "language": CountryField.LANGUAGE,
    "speak": CountryField.LANGUAGE,
    "spoken": CountryField.LANGUAGE,
    "region": CountryField.REGION,
    "continent": CountryField.CONTINENT,
    "subregion": CountryField.SUBREGION,
    "flag": CountryField.FLAG,
    "emoji": CountryField.FLAG,
    "area": CountryField.AREA,
    "size": CountryField.AREA,
    "timezone": CountryField.TIMEZONE,
    "time zone": CountryField.TIMEZONE,
    "time": CountryField.TIMEZONE,
    "border": CountryField.BORDERS,
    "borders": CountryField.BORDERS,
    "neighbour": CountryField.BORDERS,
    "neighbor": CountryField.BORDERS,
    "calling code": CountryField.CALLING_CODE,
    "phone code": CountryField.CALLING_CODE,
    "dialing code": CountryField.CALLING_CODE,
    "tell me about": CountryField.GENERAL,
    "information": CountryField.GENERAL,
    "info": CountryField.GENERAL,
}


# ── Edge-case lookup tables ────────────────────────────────────────────────

# Names that could refer to more than one real entity.
# The agent surfaces a clarification message instead of guessing.
AMBIGUOUS_COUNTRIES: Dict[str, List[str]] = {
    "georgia": [
        "Georgia (the country in the Caucasus)",
        "Georgia (US state — not a sovereign country)",
    ],
    "korea": ["South Korea", "North Korea"],
    "sudan": ["Sudan", "South Sudan"],
    "congo": [
        "Democratic Republic of the Congo (DRC)",
        "Republic of the Congo",
    ],
    "guinea": [
        "Guinea",
        "Guinea-Bissau",
        "Equatorial Guinea",
        "Papua New Guinea",
    ],
}

# Countries that no longer exist as sovereign states.
# Value is the message shown to the user.
HISTORICAL_COUNTRIES: Dict[str, str] = {
    "ussr": (
        "The **Soviet Union (USSR)** dissolved in 1991. "
        "You can ask about successor states such as **Russia**, **Ukraine**, "
        "**Kazakhstan**, or the **Baltic states**."
    ),
    "soviet union": (
        "The **Soviet Union** dissolved in 1991. "
        "Try asking about **Russia**, **Ukraine**, **Kazakhstan**, "
        "or another successor state."
    ),
    "yugoslavia": (
        "**Yugoslavia** dissolved in the early 1990s. "
        "Its successor states are: **Slovenia**, **Croatia**, "
        "**Bosnia and Herzegovina**, **Serbia**, **Montenegro**, "
        "**North Macedonia**, and **Kosovo**."
    ),
    "east germany": (
        "**East Germany (GDR)** reunified with West Germany in 1990. "
        "Try asking about **Germany**."
    ),
    "west germany": (
        "**West Germany (FRG)** reunified with East Germany in 1990. "
        "Try asking about **Germany**."
    ),
    "czechoslovakia": (
        "**Czechoslovakia** peacefully dissolved in 1993 (the 'Velvet Divorce'). "
        "You can ask about **Czechia** (Czech Republic) or **Slovakia**."
    ),
}


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    # Optional LLM settings from the frontend
    llm_provider: Optional[str] = None       # "openai" or "anthropic"
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    country: Optional[str] = None
    fields_requested: List[str] = Field(default_factory=list)
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
