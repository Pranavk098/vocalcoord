# backend/llm.py
"""Owned LLM path: Ollama (local qwen2.5:3b) with Anthropic fallback.

Template-first reply (backend/agents/response.py) stays the fast path — this
module is only reached for out-of-distribution states (no shop found, agent
gaps). PROVIDER_LLM selects the primary:

  PROVIDER_LLM=local     -> try Ollama first, fall back to Anthropic on any failure.
  PROVIDER_LLM=anthropic -> Anthropic directly (default; preserves existing behavior).

Both backends share one narrow contract: findings_block in, voice-reply string
out. Returns (text, provider_used) so the audit trail and evals can attribute
which backend actually produced the reply ("ollama" | "anthropic").
"""
import logging

import anthropic
import httpx

from backend.config import (
    OLLAMA_HOST,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    PROVIDER_LLM,
    SYNTHESIS_MAX_TOKENS,
    SYNTHESIS_MODEL,
    SYNTHESIS_TIMEOUT_SECONDS,
)

log = logging.getLogger("elmeeda")

_SYSTEM_PROMPT = """You are the Elmeeda Co-Pilot voice assistant for a professional truck driver.

Write a single voice reply (2-3 sentences max) that:
1. States the fault and urgency clearly
2. Summarizes what was arranged (shop, warranty, dispatch) from the findings given
3. Ends with a yes/no confirmation question for the driver

Rules: Be direct. No filler. Driver is behind the wheel. Never say "I" or "I've been". \
If a finding is missing (no shop found, no warranty match), say so plainly instead of guessing."""

_client: anthropic.AsyncAnthropic | None = None


def get_llm_provider() -> str:
    return PROVIDER_LLM


def _get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(timeout=SYNTHESIS_TIMEOUT_SECONDS, max_retries=1)
    return _client


async def _anthropic_synthesize(findings_block: str) -> str:
    response = await _get_anthropic_client().messages.create(
        model=SYNTHESIS_MODEL,
        max_tokens=SYNTHESIS_MAX_TOKENS,
        system=[{"type": "text", "text": _SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"Agent findings:\n{findings_block}"}],
    )
    return response.content[0].text


async def _ollama_synthesize(findings_block: str) -> str:
    prompt = f"{_SYSTEM_PROMPT}\n\nAgent findings:\n{findings_block}\n\nVoice reply:"
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
        resp = await client.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": SYNTHESIS_MAX_TOKENS},
            },
        )
        resp.raise_for_status()
        data = resp.json()
    text = (data.get("response") or "").strip()
    if not text:
        raise RuntimeError("Ollama returned empty response")
    return text


async def llm_synthesize(findings_block: str, provider: str | None = None) -> tuple[str, str]:
    """Synthesize via the owned path. Returns (text, provider_used).

    Raises the underlying exception if every configured backend fails — callers
    (response.py / graph retry node) convert that into the degraded template so
    the driver never gets dead air.
    """
    primary = (provider or PROVIDER_LLM or "anthropic").lower()
    if primary == "local":
        try:
            return await _ollama_synthesize(findings_block), "ollama"
        except Exception as e:
            log.warning("Ollama synthesis failed (%s), falling back to Anthropic", e)
            return await _anthropic_synthesize(findings_block), "anthropic"
    return await _anthropic_synthesize(findings_block), "anthropic"
