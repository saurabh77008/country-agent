"""
Node 3 — Answer Synthesis

Two modes:
  1. Template-based (default) — fast, no LLM cost, no hallucination
  2. LLM-powered (optional) — richer prose via OpenAI/Anthropic
"""

from typing import Any, Dict, List, Optional

from app.models import CountryField


def _format_population(pop: Any) -> str:
    if isinstance(pop, (int, float)):
        pop = int(pop)
        if pop >= 1_000_000_000:
            return f"{pop / 1_000_000_000:.2f} billion"
        if pop >= 1_000_000:
            return f"{pop / 1_000_000:.2f} million"
        return f"{pop:,}"
    return str(pop)


def _single_field_sentence(country: str, field: CountryField, data: dict) -> str:
    if field == CountryField.CAPITAL:
        return f"The capital of {country} is **{data.get('capital', 'unknown')}**."
    elif field == CountryField.POPULATION:
        return f"{country} has a population of approximately **{_format_population(data.get('population', 'unknown'))}**."
    elif field == CountryField.CURRENCY:
        return f"{country} uses **{data.get('currency', 'unknown')}**."
    elif field == CountryField.LANGUAGE:
        return f"The official language(s) of {country} are **{data.get('languages', 'unknown')}**."
    elif field == CountryField.AREA:
        return f"{country} covers an area of **{data.get('area_km2', 'unknown')} km²**."
    elif field == CountryField.TIMEZONE:
        return f"{country} spans the following timezone(s): **{data.get('timezones', 'unknown')}**."
    elif field == CountryField.FLAG:
        return f"The flag of {country}: {data.get('flag_emoji', '')}"
    elif field == CountryField.BORDERS:
        borders = data.get("borders", [])
        if borders:
            return f"{country} shares borders with: **{', '.join(borders)}**."
        return f"{country} has no land borders (island nation)."
    elif field == CountryField.CALLING_CODE:
        return f"The international calling code for {country} is **{data.get('calling_codes', 'unknown')}**."
    elif field == CountryField.REGION:
        sub = data.get("subregion", "")
        region = data.get("region", "unknown")
        extra = f" ({sub})" if sub else ""
        return f"{country} is located in **{region}{extra}**."
    elif field == CountryField.CONTINENT:
        return f"{country} is in **{data.get('continent', 'unknown')}**."
    else:
        return f"Here is the information I found about {country}."


def synthesise_answer(state: dict) -> dict:
    """LangGraph node — build the final human-readable answer."""
    error = state.get("error")
    if error:
        return {"answer": error}

    data = state.get("extracted_data", {})
    fields = state.get("requested_fields", [])
    country = state.get("country_name", "that country")
    official = data.get("official_name", country)

    if not data:
        return {"answer": f"I wasn't able to retrieve information about {country}."}

    field_set = set(fields)
    is_general = CountryField.GENERAL in field_set

    # Single-field: natural sentence
    if len(field_set) == 1 and not is_general:
        return {"answer": _single_field_sentence(country, fields[0], data)}

    # Multi-field or general: formatted list
    parts: List[str] = []

    if is_general:
        parts.append(f"Here's what I know about **{official}**:\n")

    if "capital" in data and (is_general or CountryField.CAPITAL in field_set):
        parts.append(f"**Capital:** {data['capital']}")
    if "population" in data and (is_general or CountryField.POPULATION in field_set):
        parts.append(f"**Population:** {_format_population(data['population'])}")
    if "currency" in data and (is_general or CountryField.CURRENCY in field_set):
        parts.append(f"**Currency:** {data['currency']}")
    if "languages" in data and (is_general or CountryField.LANGUAGE in field_set):
        parts.append(f"**Languages:** {data['languages']}")
    if "region" in data and (is_general or CountryField.REGION in field_set):
        sub = data.get("subregion", "")
        region_str = data["region"] + (f" ({sub})" if sub else "")
        parts.append(f"**Region:** {region_str}")
    if "continent" in data and CountryField.CONTINENT in field_set:
        parts.append(f"**Continent:** {data['continent']}")
    if "area_km2" in data and (is_general or CountryField.AREA in field_set):
        parts.append(f"**Area:** {data['area_km2']} km²")
    if "timezones" in data and (is_general or CountryField.TIMEZONE in field_set):
        parts.append(f"**Timezones:** {data['timezones']}")
    if "borders" in data and (is_general or CountryField.BORDERS in field_set):
        borders = data["borders"]
        parts.append(f"**Borders:** {', '.join(borders) if borders else 'None (island nation)'}")
    if "calling_codes" in data and (is_general or CountryField.CALLING_CODE in field_set):
        parts.append(f"**Calling code:** {data['calling_codes']}")
    if "flag_emoji" in data and (is_general or CountryField.FLAG in field_set):
        parts.append(f"**Flag:** {data['flag_emoji']}")

    if not parts:
        return {"answer": f"I found {official} but couldn't extract the requested information."}

    return {"answer": "\n".join(parts)}
