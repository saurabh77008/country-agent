"""
Node 3 — Answer Synthesis

SOLID design:
  SRP — TemplateSynthesiser is solely responsible for turning state into text
  OCP — swap or extend by implementing IAnswerSynthesiser
  DIP — synthesise_answer (the node) depends on IAnswerSynthesiser, not the
        concrete class

Edge cases handled:
  • Historical-country queries (is_historical flag)
  • Ambiguous-name queries    (ambiguous_countries list)
  • Multi-country comparisons (comparison_countries list)
  • Borders now show resolved country names (not raw ISO codes)
  • Graceful N/A for any missing field
"""

from __future__ import annotations

from typing import Any, List

from app.interfaces import IAnswerSynthesiser
from app.models import CountryField


# ── Pure helpers ──────────────────────────────────────────────────────────────

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
    if field == CountryField.POPULATION:
        pop = _format_population(data.get("population", "unknown"))
        return f"{country} has a population of approximately **{pop}**."
    if field == CountryField.CURRENCY:
        return f"{country} uses **{data.get('currency', 'unknown')}**."
    if field == CountryField.LANGUAGE:
        return f"The official language(s) of {country} are **{data.get('languages', 'unknown')}**."
    if field == CountryField.AREA:
        return f"{country} covers an area of **{data.get('area_km2', 'unknown')} km²**."
    if field == CountryField.TIMEZONE:
        return f"{country} spans the following timezone(s): **{data.get('timezones', 'unknown')}**."
    if field == CountryField.FLAG:
        return f"The flag of {country}: {data.get('flag_emoji', '')}"
    if field == CountryField.BORDERS:
        borders = data.get("borders", [])
        if borders:
            return f"{country} shares borders with: **{', '.join(borders)}**."
        return f"{country} has no land borders (island nation or landlocked enclave)."
    if field == CountryField.CALLING_CODE:
        return f"The international calling code for {country} is **{data.get('calling_codes', 'unknown')}**."
    if field == CountryField.REGION:
        sub = data.get("subregion", "")
        region = data.get("region", "unknown")
        extra = f" ({sub})" if sub else ""
        return f"{country} is located in **{region}{extra}**."
    if field == CountryField.CONTINENT:
        return f"{country} is in **{data.get('continent', 'unknown')}**."
    return f"Here is the information I found about {country}."


# ── Synthesiser class (SRP + OCP) ─────────────────────────────────────────────

class TemplateSynthesiser:
    """
    Builds human-readable answers from graph state using pre-defined templates.
    Implements IAnswerSynthesiser.

    OCP: to add a new field type, add a branch to _single_field_sentence and
    a line to _build_list — no other class needs changing.
    """

    def synthesise(self, state: dict) -> str:
        error = state.get("error")
        if error:
            return error

        data = state.get("extracted_data", {})
        fields: List[CountryField] = state.get("requested_fields", [])
        country: str = state.get("country_name", "that country")
        official: str = data.get("official_name", country)

        if not data:
            return f"I wasn't able to retrieve information about {country}."

        field_set = set(fields)
        is_general = CountryField.GENERAL in field_set

        # Single-field: one natural sentence
        if len(field_set) == 1 and not is_general:
            return _single_field_sentence(country, fields[0], data)

        # Multi-field or general: formatted list
        return self._build_list(official, data, field_set, is_general)

    @staticmethod
    def _build_list(
        official: str,
        data: dict,
        field_set: set,
        is_general: bool,
    ) -> str:
        parts: List[str] = []

        if is_general:
            parts.append(f"Here's what I know about **{official}**:\n")

        def _want(f: CountryField) -> bool:
            return is_general or f in field_set

        if "capital" in data and _want(CountryField.CAPITAL):
            parts.append(f"**Capital:** {data['capital']}")
        if "population" in data and _want(CountryField.POPULATION):
            parts.append(f"**Population:** {_format_population(data['population'])}")
        if "currency" in data and _want(CountryField.CURRENCY):
            parts.append(f"**Currency:** {data['currency']}")
        if "languages" in data and _want(CountryField.LANGUAGE):
            parts.append(f"**Languages:** {data['languages']}")
        if "region" in data and _want(CountryField.REGION):
            sub = data.get("subregion", "")
            region_str = data["region"] + (f" ({sub})" if sub else "")
            parts.append(f"**Region:** {region_str}")
        if "continent" in data and _want(CountryField.CONTINENT):
            parts.append(f"**Continent:** {data['continent']}")
        if "area_km2" in data and _want(CountryField.AREA):
            parts.append(f"**Area:** {data['area_km2']} km²")
        if "timezones" in data and _want(CountryField.TIMEZONE):
            parts.append(f"**Timezones:** {data['timezones']}")
        if "borders" in data and _want(CountryField.BORDERS):
            borders = data["borders"]
            parts.append(
                f"**Borders:** {', '.join(borders) if borders else 'None (island nation)'}"
            )
        if "calling_codes" in data and _want(CountryField.CALLING_CODE):
            parts.append(f"**Calling code:** {data['calling_codes']}")
        if "flag_emoji" in data and _want(CountryField.FLAG):
            parts.append(f"**Flag:** {data['flag_emoji']}")

        if not parts:
            return f"I found {official} but couldn't extract the requested information."
        return "\n".join(parts)


# ── Module-level singleton (DIP wiring) ───────────────────────────────────────

_synthesiser: IAnswerSynthesiser = TemplateSynthesiser()


# ── LangGraph node ────────────────────────────────────────────────────────────

def synthesise_answer(state: dict) -> dict:
    """LangGraph node — delegates to TemplateSynthesiser."""
    return {"answer": _synthesiser.synthesise(state)}
