# Country Information AI Agent

A production-grade AI agent built with **LangGraph** that answers questions about countries using the public [REST Countries API](https://restcountries.com/).

![Architecture](docs/architecture.png)

---

## Architecture

The agent is structured as a three-node LangGraph state machine:

```
┌──────────────────┐      ┌───────────────────┐      ┌────────────────────┐
│  1. Parse Intent │ ───▶ │ 2. Fetch Country  │ ───▶ │ 3. Synthesise      │
│                  │      │    Data (Tool)     │      │    Answer          │
│  • Extract       │      │                   │      │                    │
│    country name  │      │  • REST Countries │      │  • Template-based  │
│  • Identify      │      │    API call       │      │    NL generation   │
│    requested     │      │  • Retry + cache  │      │  • Single-field    │
│    fields        │      │  • Field          │      │    natural         │
│                  │      │    extraction     │      │    sentences       │
└──────────────────┘      └───────────────────┘      └────────────────────┘
        │                                                      │
        │──── error (no country found) ───────────────────────▶│
```

**Conditional edges** allow the graph to short-circuit: if intent parsing fails (no country detected), the agent skips the API call and goes directly to synthesis, returning a helpful error message.

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Deterministic intent parser** (no LLM) | Zero latency, zero cost, fully testable. Sufficient for the country-query domain. Swappable for LLM-based NER if scope expands. |
| **Template-based synthesis** | Produces consistent, accurate answers without hallucination risk. An LLM synthesiser could be added as an optional enhancement. |
| **In-memory TTL cache** | Reduces API calls for repeated queries. In production, swap for Redis. |
| **httpx with retries** | Resilient to transient API failures. Configurable timeout. |
| **Pydantic models throughout** | Type safety, validation, serialization. |
| **FastAPI** | Async-native, OpenAPI docs auto-generated, production-ready. |

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
# Clone the repository
git clone https://github.com/your-username/country-agent.git
cd country-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn app.server:app --reload

# Open http://localhost:8000
```

### Run Tests

```bash
pytest tests/ -v
```

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
- Retry logic with configurable timeouts

### What a real deployment would add
- **Redis cache** instead of in-memory dict
- **Rate limiting** (e.g. slowapi or API gateway)
- **Observability**: OpenTelemetry traces, Prometheus metrics
- **LLM-based intent parser** for multilingual / complex queries
- **Load balancer** + horizontal scaling
- **CI/CD pipeline** with automated tests
- **API versioning** (`/v1/query`)

---

## Known Limitations

1. **Intent parsing is keyword-based** — unusual phrasings or misspellings may not be recognised. An LLM-based parser would improve coverage.
2. **Country name extraction is heuristic** — ambiguous queries like "What about Georgia?" (US state vs country) default to the country.
3. **REST Countries API dependency** — the agent is only as reliable as the upstream API. The retry + cache layer mitigates transient failures.
4. **No multi-country comparison** — queries like "Is France bigger than Germany?" are not supported yet.
5. **English only** — the intent parser works with English queries. Multilingual support would require i18n or an LLM layer.

---

## Project Structure

```
country-agent/
├── app/
│   ├── __init__.py
│   ├── models.py          # Pydantic schemas & state
│   ├── intent_parser.py   # Node 1: parse user intent
│   ├── tools.py           # Node 2: REST Countries API
│   ├── synthesiser.py     # Node 3: answer generation
│   ├── graph.py           # LangGraph definition
│   └── server.py          # FastAPI application
├── static/
│   └── index.html         # Frontend UI
├── tests/
│   └── test_agent.py      # Unit tests
├── Dockerfile
├── requirements.txt
└── README.md
```

## License

MIT
