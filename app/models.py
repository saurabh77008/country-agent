"""Pydantic models for the Country Information Agent."""

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
