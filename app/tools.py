"""
Node 2 — Tool Invocation

Calls the REST Countries API and extracts requested fields.

SOLID design:
  SRP — RestCountriesRepository handles HTTP only; CachedCountryRepository
        handles caching only; field extraction is a separate function
  OCP — swap the data source by subclassing ICountryRepository
  DIP — fetch_country_data (the node) depends on ICountryRepository, not httpx

Edge cases handled:
  • Thread-safe in-memory cache via asyncio.Lock
  • Exact match (fullText=true) with partial-match fallback
  • Best-result selection when the API returns multiple hits
  • Borders resolved from ISO alpha-3 codes to human-readable names
  • Graceful handling of missing / malformed API fields
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.interfaces import ICountryRepository
from app.models import CountryField

# ── Constants ─────────────────────────────────────────────────────────────────

_BASE_URL = "https://restcountries.com/v3.1/name"
_ALPHA_URL = "https://restcountries.com/v3.1/alpha"
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_MAX_RETRIES = 2
_CACHE_TTL = 300


# ── Repository: HTTP layer (SRP) ──────────────────────────────────────────────

class RestCountriesRepository(ICountryRepository):
    """
    Concrete ICountryRepository that fetches data from restcountries.com.
    SRP: responsible only for HTTP communication, not caching.
    OCP: override _pick_best_result to change selection logic without
         touching the HTTP logic.
    """

    async def fetch(self, country_name: str) -> Optional[dict]:
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    resp = await client.get(
                        f"{_BASE_URL}/{country_name}",
                        params={"fullText": "true"},
                    )
                    if resp.status_code == 404:
                        resp = await client.get(
                            f"{_BASE_URL}/{country_name}",
                            params={"fullText": "false"},
                        )
                    if resp.status_code == 404:
                        return None
                    resp.raise_for_status()
                    results = resp.json()
                    if not results:
                        return None
                    return self._pick_best_result(results, country_name)

            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                if attempt == _MAX_RETRIES:
                    raise RuntimeError(
                        f"REST Countries API unavailable after "
                        f"{_MAX_RETRIES + 1} attempts: {exc}"
                    ) from exc
        return None

    @staticmethod
    def _pick_best_result(results: list, query: str) -> dict:
        """
        Select the most relevant result when the API returns multiple matches.
        Priority: exact common-name match > exact official-name match >
                  independent countries (shortest name first) > shortest name.
        """
        query_lower = query.lower().strip()

        for r in results:
            if r.get("name", {}).get("common", "").lower() == query_lower:
                return r
        for r in results:
            if r.get("name", {}).get("official", "").lower() == query_lower:
                return r

        independent = [r for r in results if r.get("independent", False)]
        pool = independent if independent else results
        pool.sort(key=lambda r: len(r.get("name", {}).get("common", "")))
        return pool[0]


# ── Repository decorator: thread-safe caching (SRP + OCP) ────────────────────

class CachedCountryRepository(ICountryRepository):
    """
    Decorator that wraps any ICountryRepository with a TTL cache.

    SRP: caching is its own concern, separate from HTTP fetching.
    OCP: wraps the inner repo without modifying it.
    LSP: can replace its inner repo anywhere ICountryRepository is expected.

    Thread-safe: uses asyncio.Lock to prevent cache stampedes under
    concurrent requests (important in production with multiple workers).
    """

    def __init__(self, inner: ICountryRepository, ttl: int = _CACHE_TTL) -> None:
        self._inner = inner
        self._ttl = ttl
        self._cache: Dict[str, Tuple[float, dict]] = {}
        self._lock = asyncio.Lock()

    async def fetch(self, country_name: str) -> Optional[dict]:
        key = country_name.lower()

        # Fast path: check without lock first (read-only)
        entry = self._cache.get(key)
        if entry and (time.monotonic() - entry[0]) < self._ttl:
            return entry[1]

        # Slow path: acquire lock, re-check, then fetch
        async with self._lock:
            entry = self._cache.get(key)
            if entry and (time.monotonic() - entry[0]) < self._ttl:
                return entry[1]

            data = await self._inner.fetch(country_name)
            if data is not None:
                self._cache[key] = (time.monotonic(), data)
            return data


# ── Border resolution ─────────────────────────────────────────────────────────

async def _resolve_border_names(border_codes: List[str]) -> List[str]:
    """
    Convert ISO 3166-1 alpha-3 border codes to human-readable country names
    using a single batch request to the REST Countries alpha endpoint.

    Falls back to returning the original codes if the request fails.
    """
    if not border_codes:
        return []
    codes_param = ",".join(border_codes).lower()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=4.0)) as client:
            resp = await client.get(
                _ALPHA_URL,
                params={"codes": codes_param, "fields": "name"},
            )
            if resp.status_code == 200:
                data = resp.json()
                names = sorted(
                    r.get("name", {}).get("common", "")
                    for r in data
                    if r.get("name", {}).get("common")
                )
                return names if names else border_codes
    except Exception:
        pass
    return border_codes  # Graceful fallback: return ISO codes as-is


# ── Field extraction (pure function, SRP) ─────────────────────────────────────

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
    """Pull requested fields from the API response dict."""
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
            extracted["area_km2"] = f"{area:,.0f}" if area is not None else "N/A"
        elif f == CountryField.TIMEZONE:
            extracted["timezones"] = ", ".join(raw.get("timezones", ["N/A"]))
        elif f == CountryField.BORDERS:
            # Store raw codes here; caller resolves to names if needed
            extracted["borders"] = raw.get("borders", [])
        elif f == CountryField.CALLING_CODE:
            idd = raw.get("idd", {})
            root = idd.get("root", "")
            suffixes = idd.get("suffixes", [])
            codes = [f"{root}{s}" for s in suffixes] if root else []
            extracted["calling_codes"] = ", ".join(codes) if codes else "N/A"

    extracted["official_name"] = (
        raw.get("name", {}).get("official")
        or raw.get("name", {}).get("common", "")
    )
    return extracted


# ── Module-level repository instance (DIP wiring) ────────────────────────────

_repo: ICountryRepository = CachedCountryRepository(RestCountriesRepository())


# ── LangGraph node ────────────────────────────────────────────────────────────

async def fetch_country_data(state: dict) -> dict:
    """
    LangGraph node — calls the country repository and extracts requested data.

    Skips the API call if a prior node already set an error (e.g. historical
    country, ambiguous name, comparison query).
    """
    if state.get("error"):
        return {}

    country = state.get("country_name")
    fields: List[CountryField] = state.get("requested_fields", [])

    if not country:
        return {"error": "No country identified to look up."}

    try:
        raw = await _repo.fetch(country)
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

    # Resolve border codes → names when borders are explicitly requested
    borders_requested = (
        CountryField.BORDERS in fields or CountryField.GENERAL in fields
    )
    if borders_requested and extracted.get("borders"):
        extracted["borders"] = await _resolve_border_names(extracted["borders"])

    return {
        "raw_api_response": raw,
        "extracted_data": extracted,
    }
