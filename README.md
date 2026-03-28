# Country Information AI Agent

A production-grade AI agent built with **LangGraph** that answers questions about countries using the public [REST Countries API](https://restcountries.com/).

---

## Architecture

The agent is structured as a three-node LangGraph state machine:

```
┌──────────────────────┐      ┌──────────────────────┐      ┌──────────────────────┐
│  1. Parse Intent     │ ───▶ │ 2. Fetch Country     │ ───▶ │ 3. Synthesise        │
│                      │      │    Data (Tool)        │      │    Answer            │
│  • Alias extraction  │      │                      │      │                      │
│  • Known-list match  │      │  • REST Countries    │      │  • Template-based    │
│  • Fuzzy / typo fix  │      │    API call          │      │    NL generation     │
│  • Historical check  │      │  • Thread-safe cache │      │  • Single-field      │
│  • Ambiguity check   │      │  • Border name       │      │    natural sentences │
│  • Comparison detect │      │    resolution        │      │  • Edge-case msgs    │
└──────────────────────┘      └──────────────────────┘      └──────────────────────┘
          │                                                            │
          │──── error (historical / ambiguous / comparison / none) ──▶│
```

**Conditional edges** allow the graph to short-circuit: if intent parsing detects an error condition, the agent skips the API call and returns a helpful message directly.

### SOLID Design

| Principle | How it's applied |
|-----------|-----------------|
| **SRP** | Each class has one job: `RestCountriesRepository` handles HTTP; `CachedCountryRepository` handles caching; `TemplateSynthesiser` builds answers. |
| **OCP** | Add a new extraction strategy by writing a new class and passing it to `_CompositeCountryExtractor` — existing code is unchanged. Add aliases to `_COUNTRY_ALIASES` dict without touching any extractor. |
| **LSP** | `CachedCountryRepository` wraps `RestCountriesRepository` and can replace it anywhere `ICountryRepository` is expected. All extractor classes satisfy `ICountryExtractor`. |
| **ISP** | `ICountryExtractor`, `IFieldExtractor`, `ICountryRepository`, and `IAnswerSynthesiser` are four focused protocols — nothing is forced to implement methods it doesn't need. |
| **DIP** | `parse_intent` depends on `ICountryExtractor`/`IFieldExtractor`. `fetch_country_data` depends on `ICountryRepository`. Concrete classes are wired at module level and injected as singletons. |

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Deterministic intent parser** (no LLM) | Zero latency, zero cost, fully testable. Sufficient for the country-query domain. Swappable for LLM-based NER if scope expands. |
| **Fuzzy matching via `difflib`** | Handles typos ("Frence" → France) with no extra dependencies. Cutoff of 0.82 balances recall vs false positives. |
| **Template-based synthesis** | Consistent, accurate answers with no hallucination risk. Optional LLM enhancement available for richer prose. |
| **`asyncio.Lock`-protected cache** | Thread-safe under concurrent requests; prevents cache stampedes. Swap for Redis in multi-process deployments. |
| **Single batch border resolution** | One request to `/alpha?codes=…` resolves all border ISO codes to names instead of N sequential requests. |
| **httpx with retries** | Resilient to transient API failures. Exact-match (`fullText=true`) with partial-match fallback. |

---

## Edge Cases Handled

| Edge Case | Behaviour |
|-----------|-----------|
| **Possessives** — "Japan's capital" | `'s` stripped during normalisation before extraction |
| **Dot acronyms** — "U.S.A.", "U.A.E." | Dots removed so alias table matches "usa", "uae" |
| **Typos / misspellings** — "Frence", "Germanu" | `_FuzzyExtractor` uses `difflib.get_close_matches` (cutoff 0.82) |
| **Aliases** — USA, UK, UAE, Burma, Siam, Persia, Zaire, PNG, DPRK, … | Mapped to canonical names in `_COUNTRY_ALIASES` (55+ entries) |
| **Ambiguous names** — "Georgia", "Korea", "Sudan", "Congo", "Guinea" | Agent returns a clarification message listing all candidates |
| **Historical / defunct states** — USSR, Yugoslavia, East/West Germany, Czechoslovakia | Agent returns a helpful redirect message naming successor states |
| **Multi-country comparisons** — "France vs Germany", "compare India and China" | Detected via regex; graceful "not yet supported" message with countries listed |
| **Border codes → names** | ISO alpha-3 codes (e.g. `GBR`, `DEU`) resolved to readable names in one batch API call |
| **Thread-safe cache** | `asyncio.Lock` prevents race conditions under concurrent requests |
| **API unavailable** | 3 retry attempts with backoff before returning an error |
| **API returns multiple results** | Best-result selection: exact name match > independent countries > shortest name |

---

## Supported Queries

| Field | Example Questions |
|-------|-------------------|
| Capital | "What is the capital of France?" |
| Population | "How many people live in India?" |
| Currency | "What currency does Japan use?" |
| Languages | "What languages are spoken in Switzerland?" |
| Region | "What region is Brazil in?" |
| Area | "How big is Canada?" |
| Timezones | "What timezone is Australia in?" |
| Borders | "What countries border Germany?" |
| Calling code | "What is the calling code for Mexico?" |
| Flag | "Show me the flag of Italy" |
| General | "Tell me about Nigeria" |

Multiple fields can be combined: *"What is the capital and population of Brazil?"*

---

## Quick Start

### Prerequisites
- Python 3.11+

### Install & Run

```bash
git clone https://github.com/your-username/country-agent.git
cd country-agent

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

uvicorn app.server:app --reload
# Open http://localhost:8000
```

### Run Tests

```bash
pytest tests/ -v
```

68 unit tests covering happy paths, all edge-case detectors, and SOLID interface compliance.

### Docker

```bash
docker build -t country-agent .
docker run -p 8000:8000 country-agent
```

---

## API Reference

### `POST /api/query`

**Request:**
```json
{
  "question": "What is the capital of France?"
}
```

**Response:**
```json
{
  "answer": "The capital of France is **Paris**.",
  "country": "France",
  "fields_requested": ["capital"],
  "data": {
    "capital": "Paris",
    "official_name": "French Republic"
  },
  "error": null
}
```

**Error response (ambiguous name):**
```json
{
  "answer": "**\"Georgia\"** could refer to multiple entities: **Georgia (the country in the Caucasus)**, **Georgia (US state — not a sovereign country)**. Please be more specific.",
  "error": "..."
}
```

**Error response (historical country):**
```json
{
  "answer": "The **Soviet Union (USSR)** dissolved in 1991. You can ask about successor states such as **Russia**, **Ukraine**, **Kazakhstan**, or the **Baltic states**.",
  "error": "..."
}
```

### `GET /api/health`

Returns `{"status": "ok"}`.

---

## Production Considerations

### What's production-ready now
- Structured logging with request timing
- Input validation (Pydantic)
- Graceful error handling at every layer
- CORS configured
- Health check endpoint
- Dockerised deployment
- Thread-safe TTL cache with `asyncio.Lock`
- Retry logic with configurable timeouts
- SOLID-compliant architecture (interfaces in `app/interfaces.py`)

### What a real deployment would add
- **Redis cache** instead of in-memory dict (required for multi-process deployments)
- **Rate limiting** (e.g. slowapi or API gateway)
- **Observability**: OpenTelemetry traces, Prometheus metrics
- **LLM-based intent parser** for multilingual / complex queries
- **Load balancer** + horizontal scaling
- **CI/CD pipeline** with automated tests
- **API versioning** (`/v1/query`)

---

## Known Limitations

1. **English only** — the intent parser works with English queries. Multilingual support would require i18n keyword maps or an LLM layer.
2. **No multi-country comparison** — queries like "Is France bigger than Germany?" are detected and return a graceful error rather than an answer.
3. **REST Countries API dependency** — the agent is only as reliable as the upstream API. The retry + cache layer mitigates transient failures.
4. **Fallback extractor can be noisy** — if all other extractors fail, the agent tries to guess a country from remaining tokens. The API will then return a 404 for invalid guesses.

---

## Project Structure

```
country-agent/
├── app/
│   ├── __init__.py
│   ├── interfaces.py      # SOLID abstractions (ICountryExtractor, ICountryRepository, …)
│   ├── models.py          # Pydantic schemas, AMBIGUOUS_COUNTRIES, HISTORICAL_COUNTRIES
│   ├── intent_parser.py   # Node 1: extractor classes + edge-case detectors
│   ├── tools.py           # Node 2: RestCountriesRepository, CachedCountryRepository
│   ├── synthesiser.py     # Node 3: TemplateSynthesiser
│   ├── graph.py           # LangGraph state machine
│   ├── llm_integration.py # Optional LLM answer enhancement
│   └── server.py          # FastAPI application
├── static/
│   └── index.html         # Frontend UI
├── tests/
│   └── test_agent.py      # 68 unit tests
├── Dockerfile
├── requirements.txt
└── README.md
```

## License

MIT
