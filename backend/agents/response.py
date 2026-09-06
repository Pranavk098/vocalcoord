# backend/agents/response.py
"""Voice reply synthesis. Template-first: when all four agents resolved cleanly (the
common case, and the whole demo path), render the reply from structured state in
microseconds — no LLM call, no hallucination risk, identical phrasing every time
(a feature for a driver hearing this at 65 mph). The LLM is reserved for genuinely
out-of-distribution states: no shop found, or anything else incomplete. If the LLM
call itself fails or times out, fall back to a degraded template so the driver never
gets dead air.

Owned LLM path (HYBRID): PROVIDER_LLM=local tries Ollama qwen2.5:3b first with
Anthropic fallback; PROVIDER_LLM=anthropic (default) calls Anthropic directly.
See backend/llm.py and docs/adr/0005-hybrid-owned-stt-llm.md.
"""
import asyncio
import logging

from backend.config import SYNTHESIS_MAX_RETRIES
from backend.tools.j1939 import lookup_fault, parse_fault_code

log = logging.getLogger("elmeeda")


def _fault_desc(state: dict) -> str:
    parsed = parse_fault_code(state.get("fault_code"))
    if not parsed:
        return "Vehicle fault detected"
    fault = lookup_fault(parsed[0])
    return fault["plain_english"] if fault else "Vehicle fault detected"


def _is_complete_fault_response(state: dict) -> bool:
    return bool(state.get("best_shop") and state.get("wellness_response") and state.get("dispatch_payload"))


def is_template_path(state: dict) -> bool:
    """True when the reply renders from the deterministic template (no LLM)."""
    return _is_complete_fault_response(state)


def _bay_phrase(shop: dict) -> str:
    bay_time = shop.get("open_bay_time", "")
    when = "now" if bay_time.strip().lower() == "now" else f"at {bay_time}"
    return f"Bay booked at {shop['name']}, {shop['distance_miles']} miles ahead, {when}."


def _hos_tier(wellness_response: str) -> str:
    if wellness_response.startswith("["):
        return wellness_response[1:wellness_response.index("]")]
    return ""


def _render_template(state: dict) -> str:
    parts = [_fault_desc(state)]

    shop = state["best_shop"]
    parts.append(_bay_phrase(shop))

    warranty = state.get("warranty_findings")
    if warranty:
        cost_note = "at no cost to you" if warranty.get("labor_included") else f"with a ${warranty['claim_value']} claim"
        parts.append(f"Repair is covered under {warranty['coverage']} {cost_note}.")
    else:
        parts.append("No warranty coverage applies to this repair.")

    dispatch = state["dispatch_payload"]
    parts.append(f"Dispatch notified on {dispatch['load_number']} with a {dispatch['delay_estimate_hours']}-hour delay.")

    tier = _hos_tier(state["wellness_response"])
    if tier in ("CRITICAL", "SEVERE"):
        parts.append(f"HOS {tier} — you will not have legal drive time left after this stop; plan a reset with dispatch.")

    parts.append("Ready to set nav — yes or no?")
    return " ".join(parts)


def _render_degraded_template(state: dict) -> str:
    fault = _fault_desc(state)
    hos = state.get("wellness_response") or ""
    tier = _hos_tier(hos)
    pieces = [f"{fault} I'm having trouble pulling every detail together right now."]
    if tier in ("CRITICAL", "SEVERE"):
        pieces.append(f"HOS {tier} — coordinate directly with dispatch before continuing.")
    pieces.append("Please contact dispatch, or repeat the fault code and I'll try again.")
    return " ".join(pieces)


def _findings_block(state: dict) -> str:
    context_parts = [_fault_desc(state)]

    if state.get("best_shop"):
        shop = state["best_shop"]
        context_parts.append(
            f"Shop: {shop['name']}, {shop['distance_miles']} miles ahead, "
            f"open bay at {shop['open_bay_time']}, has required part: {shop.get('has_def_pump', False)}"
        )
    else:
        context_parts.append("Shop: no certified shop found within radius.")

    if state.get("warranty_findings"):
        w = state["warranty_findings"]
        context_parts.append(f"Warranty: {w['coverage']}, claim value ${w['claim_value']}, labor included: {w['labor_included']}")
    else:
        context_parts.append("Warranty: no coverage found.")

    if state.get("dispatch_payload"):
        d = state["dispatch_payload"]
        context_parts.append(f"Dispatch notified: {d['load_number']} delayed ~{d['delay_estimate_hours']} hours")

    if state.get("wellness_response"):
        context_parts.append(f"HOS status: {state['wellness_response']}")

    return "\n".join(f"- {c}" for c in context_parts)


async def build_voice_reply_with_meta(state: dict) -> tuple[str, str]:
    """Returns (reply, source) where source is template | llm:<backend> | degraded.

    LLM budget: 1 initial attempt + SYNTHESIS_MAX_RETRIES retries (graph retry
    node mirrors this budget across synthesize -> synthesize_retry edges).
    """
    intent = state.get("intent") or ""
    # Per-intent deterministic fast paths — no LLM for single-agent turns.
    if intent == "nav_confirm" and state.get("voice_reply"):
        return state["voice_reply"], state.get("reply_source") or "template:nav_confirm"
    if intent == "wellness_check" and state.get("wellness_response"):
        return f"{state['wellness_response']} Anything else I can help with — yes or no?", "template:wellness"
    if intent == "warranty_query":
        w = state.get("warranty_findings")
        if w:
            cost = "at no cost to you" if w.get("labor_included") else f"with a ${w['claim_value']} claim"
            return f"Repair is covered under {w['coverage']} {cost}. Anything else — yes or no?", "template:warranty"
        return "No warranty coverage applies to this repair. Anything else — yes or no?", "template:warranty"
    if intent == "dispatch_update" and state.get("dispatch_payload"):
        d = state["dispatch_payload"]
        return (
            f"Dispatch updated on {d['load_number']} with a {d['delay_estimate_hours']}-hour delay. "
            "Anything else — yes or no?"
        ), "template:dispatch"
    if intent == "shop_search":
        shop = state.get("best_shop")
        if shop:
            return f"{_bay_phrase(shop)} Ready to set nav — yes or no?", "template:shop"
        return "No certified shop found within range. Want me to widen the search — yes or no?", "template:shop"
    if _is_complete_fault_response(state):
        return _render_template(state), "template"
    from time import monotonic

    from backend.latency import BUDGETS_MS
    from backend.llm import llm_synthesize

    attempts = 1 + max(0, SYNTHESIS_MAX_RETRIES)
    # Overall OOD budget: retries + backoff must never exceed the LLM cap
    # (default 2000ms) — a slow LLM degrades to template, never stalls.
    # The wait_for here caps the attempt itself (a hung backend or a future
    # provider that skips its own timeout); llm_synthesize enforces the same
    # budget internally, so the tighter of the two always wins.
    deadline = monotonic() + BUDGETS_MS["synthesize_llm"] / 1000.0
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        try:
            text, backend_used = await asyncio.wait_for(
                llm_synthesize(_findings_block(state)), timeout=remaining
            )
            return text, f"llm:{backend_used}"
        except Exception as e:  # noqa: BLE001 — any LLM failure degrades, never dead air
            last_error = e
            log.warning("LLM synthesis attempt %d/%d failed: %s", attempt, attempts, e)
            if attempt < attempts and monotonic() + 0.2 * attempt < deadline:
                await asyncio.sleep(0.2 * attempt)
            else:
                break
    log.warning("LLM synthesis failed, using degraded template: %s", last_error)
    return _render_degraded_template(state), "degraded"


async def build_voice_reply(state: dict) -> str:
    reply, _ = await build_voice_reply_with_meta(state)
    return reply
