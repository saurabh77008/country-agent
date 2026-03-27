"""
FastAPI application — Country Information Agent

Endpoints:
  POST /api/query   — process a user question (optional LLM enhancement)
  GET  /api/health  — health check
  GET  /            — serve the frontend
"""

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.graph import agent
from app.models import QueryRequest, QueryResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("country_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Country Information Agent started")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Country Information Agent",
    description="AI agent that answers questions about countries using LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent.parent / "static"


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    logger.info("%s %s — %d (%.1f ms)", request.method, request.url.path, response.status_code, elapsed)
    return response


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """Run the LangGraph agent. Optionally enhance with LLM."""
    logger.info("Query: %s", req.question)

    try:
        result = await agent.ainvoke({"user_query": req.question})
    except Exception:
        logger.exception("Agent execution failed")
        return QueryResponse(
            answer="Something went wrong while processing your request. Please try again.",
            error="internal_error",
        )

    answer = result.get("answer", "")
    extracted = result.get("extracted_data", {})
    country = result.get("country_name")
    error = result.get("error")

    # If LLM settings provided and we have data, enhance the answer
    if req.llm_api_key and req.llm_provider and extracted and not error:
        try:
            from app.llm_integration import llm_synthesise
            llm_answer = await llm_synthesise(
                question=req.question,
                country=country or "",
                data=extracted,
                provider=req.llm_provider,
                api_key=req.llm_api_key,
                model=req.llm_model,
            )
            if llm_answer:
                answer = llm_answer
        except Exception:
            logger.exception("LLM enhancement failed, using template answer")

    return QueryResponse(
        answer=answer,
        country=country,
        fields_requested=[
            f.value if hasattr(f, "value") else str(f)
            for f in result.get("requested_fields", [])
        ],
        data=extracted,
        error=error,
    )


# Static files & SPA fallback
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(str(STATIC_DIR / "index.html"))


@app.exception_handler(422)
async def validation_error(request: Request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "answer": "Invalid request. Please send a JSON body with a 'question' field.",
            "error": "validation_error",
        },
    )
