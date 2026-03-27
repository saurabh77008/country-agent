"""
Node 2 — Tool Invocation

Calls the REST Countries API and extracts requested fields.
Key fix: uses fullText=true for exact match and picks the best result
when multiple are returned (prefers the country whose common name
matches the query, not territories).
"""

import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.models import CountryField

_BASE_URL = "https://restcountries.com/v3.1/name"
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_MAX_RETRIES = 2

_cache: Dict[str, Tuple[float, dict]] = {}
_CACHE_TTL = 300


def _get_cached(country: str) -> Optional[dict]:
    entry = _cache.get(country.lower())
    if entry and (time.time() - entry[0]) < _CACHE_TTL:
        return entry[1]
    return None


def _set_cache(country: str, data: dict) -> None:
    _cache[country.lower()] = (time.time(), data)


def _pick_best_result(results: list, query: str) -> dict:
    """Pick the best matching country from API results.

    The REST Countries API returns partial matches. For "India" it may
    return both "India" and "British Indian Ocean Territory".
    We prefer the result whose common name exactly matches the query.
    """
    query_lower = query.lower().strip()

    # 1. Exact match on common name
    for r in results:
        common = r.get("name", {}).get("common", "").lower()
        if common == query_lower:
            return r

    # 2. Exact match on official name
    for r in results:
        official = r.get("name", {}).get("official", "").lower()
        if official == query_lower:
            return r

    # 3. Prefer independent countries over territories
    independent = [r for r in results if r.get("independent", False)]
    if independent:
        # Among independent countries, pick the one with shortest name
        # (closer match to query)
        independent.sort(key=lambda r: len(r.get("name", {}).get("common", "")))
        return independent[0]

    # 4. Pick by shortest common name (closest match)
    results_sorted = sorted(results, key=lambda r: len(r.get("name", {}).get("common", "")))
    return results_sorted[0]


async def _fetch_country(country: str) -> Optional[dict]:
    """Fetch country data from REST Countries API."""
    cached = _get_cached(country)
    if cached:
        return cached

    for attempt in range(_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                # Try exact match first
                resp = await client.get(f"{_BASE_URL}/{country}", params={"fullText": "true"})

                if resp.status_code == 404:
                    # Fall back to partial match
                    resp = await client.get(f"{_BASE_URL}/{country}", params={"fullText": "false"})

                if resp.status_code == 404:
                    return None

                resp.raise_for_status()
                results = resp.json()
                if not results:
                    return None

                # Pick the best match (not just first result!)
                data = _pick_best_result(results, country)
                _set_cache(country, data)
                return data

        except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            if attempt == _MAX_RETRIES:
                raise RuntimeError(
                    f"REST Countries API unavailable after {_MAX_RETRIES + 1} attempts: {exc}"
                ) from exc

    return None


def _format_currencies(currencies: dict) -> str:
    parts = []
    for code, info in currencies.items():
        name = info.get("name", code)
        symbol = info.get("symbol", "")
        parts.append(f"{name} ({code})" + (f" — symbol: {symbol}" if symbol else ""))
    return ", ".join(parts)


def _format_languages(languages: dict) -> str:
    return ", ".join(sorted(languages.values()))


def _extract_fields(raw: dict, fields: List[CountryField]) -> Dict[str, Any]:
    """Pull requested fields from API response."""
    extracted: Dict[str, Any] = {}
    field_set = set(fields)

    if CountryField.GENERAL in field_set:
        field_set = set(CountryField)

    for f in field_set:
        if f == CountryField.CAPITAL:
            caps = raw.get("capital", [])
            extracted["capital"] = caps[0] if caps else "N/A"
        elif f == CountryField.POPULATION:
            extracted["population"] = raw.get("population", "N/A")
        elif f == CountryField.CURRENCY:
            currencies = raw.get("currencies", {})
            extracted["currency"] = _format_currencies(currencies) if currencies else "N/A"
        elif f == CountryField.LANGUAGE:
            langs = raw.get("languages", {})
            extracted["languages"] = _format_languages(langs) if langs else "N/A"
        elif f == CountryField.REGION:
            extracted["region"] = raw.get("region", "N/A")
        elif f == CountryField.SUBREGION:
            extracted["subregion"] = raw.get("subregion", "N/A")
        elif f == CountryField.CONTINENT:
            continents = raw.get("continents", [])
            extracted["continent"] = ", ".join(continents) if continents else "N/A"
        elif f == CountryField.FLAG:
            extracted["flag_emoji"] = raw.get("flag", "")
            flags = raw.get("flags", {})
            extracted["flag_url"] = flags.get("svg", flags.get("png", ""))
        elif f == CountryField.AREA:
            area = raw.get("area")
            extracted["area_km2"] = f"{area:,.0f}" if area else "N/A"
        elif f == CountryField.TIMEZONE:
            extracted["timezones"] = ", ".join(raw.get("timezones", ["N/A"]))
        elif f == CountryField.BORDERS:
            extracted["borders"] = raw.get("borders", [])
        elif f == CountryField.CALLING_CODE:
            idd = raw.get("idd", {})
            root = idd.get("root", "")
            suffixes = idd.get("suffixes", [])
            codes = [f"{root}{s}" for s in suffixes] if root else []
            extracted["calling_codes"] = ", ".join(codes) if codes else "N/A"

    extracted["official_name"] = raw.get("name", {}).get("official", raw.get("name", {}).get("common", ""))

    return extracted


async def fetch_country_data(state: dict) -> dict:
    """LangGraph node — call REST Countries API and extract requested data."""
    if state.get("error"):
        return {}

    country = state.get("country_name")
    fields = state.get("requested_fields", [])

    if not country:
        return {"error": "No country identified to look up."}

    try:
        raw = await _fetch_country(country)
    except RuntimeError as exc:
        return {"error": str(exc)}

    if raw is None:
        return {
            "error": (
                f"I couldn't find a country matching \"{country}\". "
                "Please check the spelling and try again."
            )
        }

    extracted = _extract_fields(raw, fields)

    return {
        "raw_api_response": raw,
        "extracted_data": extracted,
    }
