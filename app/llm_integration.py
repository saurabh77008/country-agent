"""
Optional LLM Integration

When the user provides an API key via the UI, this module enhances
the agent with LLM-powered answer synthesis. The LLM receives the
structured data from the REST Countries API and produces a richer,
more conversational answer.

This does NOT replace the data source — the REST Countries API is
always the source of truth. The LLM only reformats the answer.
"""

import json
from typing import Any, Dict, Optional

import httpx


async def llm_synthesise(
    question: str,
    country: str,
    data: Dict[str, Any],
    provider: str,
    api_key: str,
    model: Optional[str] = None,
) -> Optional[str]:
    """Use an LLM to produce a richer answer from structured data.

    Returns the LLM answer string, or None if the call fails.
    """
    data_str = json.dumps(data, indent=2, default=str)

    system_prompt = (
        "You are a helpful country information assistant. "
        "You will receive a user's question and factual data retrieved from the REST Countries API. "
        "Use ONLY the provided data to answer — do not make up information. "
        "Give a clear, concise, conversational answer. "
        "Use markdown bold for key values."
    )

    user_prompt = (
        f"User question: {question}\n\n"
        f"Country: {country}\n\n"
        f"Data from REST Countries API:\n{data_str}\n\n"
        f"Please answer the user's question using only this data."
    )

    try:
        if provider == "openai":
            return await _call_openai(system_prompt, user_prompt, api_key, model or "gpt-4o-mini")
        elif provider == "anthropic":
            return await _call_anthropic(system_prompt, user_prompt, api_key, model or "claude-sonnet-4-20250514")
        else:
            return None
    except Exception:
        return None


async def _call_openai(system: str, user: str, api_key: str, model: str) -> Optional[str]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": 500,
                "temperature": 0.3,
            },
        )
        resp.raise_for_status()
        result = resp.json()
        return result["choices"][0]["message"]["content"]


async def _call_anthropic(system: str, user: str, api_key: str, model: str) -> Optional[str]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "system": system,
                "messages": [
                    {"role": "user", "content": user},
                ],
                "max_tokens": 500,
            },
        )
        resp.raise_for_status()
        result = resp.json()
        return result["content"][0]["text"]
