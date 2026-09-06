# backend/tests/test_parallel_budgets.py
"""2nd-cycle revamp: timeout budgets + graceful degradation.

Contract under test:
  - run_with_budget never raises; slow/crashed branches yield flagged fallbacks.
  - fault_branch survives a hung agent: turn still synthesizes, slow branch is
    named in _degraded_branches, other branches' data is intact.
  - LLM hang past its budget degrades to template (never dead air, never stall).
  - Webhook turn budget degrades a stalled graph to a 503-free degraded reply.
  - Latency budgets table exposes every stage budget from the revamp spec.
  - TTL caches (fault decode, shop rank) hit on repeat and respect geo/HOS keys.
"""
import asyncio
from time import monotonic, perf_counter

import pytest
from httpx import ASGITransport, AsyncClient

from backend.latency import BUDGETS_MS, run_with_budget


def _base_state(**overrides):
    state = {
        "conversation_id": "budget_test",
        "trace_id": "trace_budget",
        "t0": monotonic(),
        "tool_name": "trigger_fault_response",
        "fault_code": "SPN 4334 FMI 18",
        "fault_severity": "red_stop",
        "driver_location": {"lat": 39.96, "lon": -82.99, "city": "Columbus, OH"},
        "hos_hours_remaining": 4.5,
        "load_number": "LOAD-BUDGET",
        "intent": "",
        "active_agents": [],
        "shop_results": [],
        "best_shop": None,
        "warranty_findings": None,
        "wellness_response": "",
        "dispatch_payload": None,
        "voice_reply": "",
        "parameters": {},
    }
    state.update(overrides)
    return state


def test_budgets_table_has_all_stages():
    assert BUDGETS_MS["parse"] <= 50.0
    assert BUDGETS_MS["branches"] <= 400.0
    assert BUDGETS_MS["synthesize_template"] <= 10.0
    assert BUDGETS_MS["synthesize_llm"] <= 2000.0
    assert BUDGETS_MS["sse_first_byte"] <= 600.0


@pytest.mark.asyncio
async def test_run_with_budget_returns_fallback_on_timeout():
    async def _slow():
        await asyncio.sleep(5.0)
        return {"x": 1}

    out = await run_with_budget(_slow(), budget_ms=50, fallback={"x": 0}, label="slow")
    assert out["x"] == 0
    assert out["degraded"] is True


@pytest.mark.asyncio
async def test_run_with_budget_returns_fallback_on_crash():
    async def _boom():
        raise RuntimeError("branch exploded")

    out = await run_with_budget(_boom(), budget_ms=500, fallback={"x": 0}, label="boom")
    assert out["x"] == 0
    assert out["degraded"] is True


@pytest.mark.asyncio
async def test_run_with_budget_passes_through_fast_branch():
    async def _fast():
        return {"x": 1}

    out = await run_with_budget(_fast(), budget_ms=500, fallback={"x": 0}, label="fast")
    assert out == {"x": 1}


@pytest.mark.asyncio
async def test_fault_branch_degrades_hung_warranty_but_keeps_template(monkeypatch):
    """Hanging warranty_scout must not stall the turn: template path needs
    best_shop + wellness + dispatch only, so the reply stays template-sourced
    and the slow branch is flagged."""
    from backend.graph import fault_branch

    monkeypatch.setitem(BUDGETS_MS, "branch_each", 80.0)

    # fault_branch imports runners inside its body at call time, so patch the
    # source module it imports from.
    import backend.agents.warranty_scout as ws_mod

    async def _hung2(state):
        await asyncio.sleep(5.0)
        return {"warranty_findings": {"coverage": "X"}}

    monkeypatch.setattr(ws_mod, "run_warranty_scout", _hung2)

    result = await fault_branch(_base_state())
    assert result["best_shop"] is not None  # shop branch unaffected
    assert result["wellness_response"]  # wellness branch unaffected
    assert result["dispatch_payload"] is not None
    assert result.get("_degraded_branches") == ["warranty_scout"]

    from backend.agents.response import build_voice_reply_with_meta

    reply, source = await build_voice_reply_with_meta({**result, "intent": "fault_detected"})
    assert source == "template"
    assert reply.strip().endswith("?")


@pytest.mark.asyncio
async def test_llm_hang_degrades_fast(monkeypatch):
    """OOD state + hung LLM must degrade within the LLM budget, not stall."""
    import backend.agents.response as resp_mod

    monkeypatch.setitem(BUDGETS_MS, "synthesize_llm", 120.0)

    # Hang the backends below llm_synthesize so the test exercises the REAL
    # budget enforcement (wait_for inside llm_synthesize + the retry deadline
    # in build_voice_reply_with_meta), not a mock that skips timeouts.
    async def _hung_backend(*a, **k):
        await asyncio.sleep(5.0)
        return "never"

    monkeypatch.setattr("backend.llm._ollama_synthesize", _hung_backend)
    monkeypatch.setattr("backend.llm._anthropic_synthesize", _hung_backend)
    # Incomplete state forces the OOD LLM path (no best_shop).
    state = _base_state(best_shop=None, intent="fault_detected",
                        wellness_response="[CLEAR] ok",
                        dispatch_payload={"load_number": "L", "delay_estimate_hours": 2})
    t0 = perf_counter()
    reply, source = await resp_mod.build_voice_reply_with_meta(state)
    dt_ms = (perf_counter() - t0) * 1000
    assert source == "degraded"
    assert reply
    assert dt_ms < 2000.0


@pytest.mark.asyncio
async def test_webhook_turn_budget_degrades_stalled_graph(monkeypatch):
    """A graph stall past the turn budget still returns 200 + degraded text."""
    from unittest.mock import AsyncMock

    from backend.main import app

    async def _stall(*a, **k):
        await asyncio.sleep(5.0)
        return {"voice_reply": "never"}

    monkeypatch.setitem(BUDGETS_MS, "turn", 150.0)
    monkeypatch.setattr("backend.main.graph.ainvoke", AsyncMock(side_effect=_stall))

    payload = {
        "type": "tool_call", "conversation_id": "conv_turn_budget_test",
        "tool_name": "trigger_fault_response",
        "parameters": {"fault_code": "SPN 4334 FMI 18", "driver_location": "Columbus, OH",
                       "hos_hours_remaining": 4.5, "load_number": "LOAD-TB"},
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/webhook/tool-call", json=payload)
    assert resp.status_code == 200
    assert "having trouble" in resp.json()["result"]


def test_fault_decode_cache_hits_on_repeat():
    from backend import cache as cache_mod
    from backend.tools.j1939 import lookup_fault_cached

    cache_mod.fault_decode_cache.clear()
    first = lookup_fault_cached("SPN 4334 FMI 18")
    assert first[0] == (4334, 18) and first[1] is not None
    assert cache_mod.fault_decode_cache.stats()["misses"] == 1
    second = lookup_fault_cached("SPN 4334 FMI 18")
    assert second == first
    assert cache_mod.fault_decode_cache.stats()["hits"] == 1


def test_shop_rank_cache_keyed_by_geo_and_hos():
    from backend import cache as cache_mod
    from backend.tools.shop_db import search_shops_cached

    cache_mod.shop_rank_cache.clear()
    shops_a, best_a = search_shops_cached(
        needs_def_pump=True, max_distance=25, geo_key="city:columbus, oh", hos_hours_remaining=4.5)
    assert shops_a and best_a is not None
    shops_b, best_b = search_shops_cached(
        needs_def_pump=True, max_distance=25, geo_key="city:columbus, oh", hos_hours_remaining=4.5)
    assert (shops_b, best_b) == (shops_a, best_a)
    assert cache_mod.shop_rank_cache.stats()["hits"] == 1
    # Different metro = different key = miss, not a poisoned Columbus ranking.
    shops_c, _ = search_shops_cached(
        needs_def_pump=True, max_distance=25, geo_key="city:phoenix", hos_hours_remaining=4.5)
    assert shops_c == shops_a  # fixture has one shop list; keying still verified by miss count
    assert cache_mod.shop_rank_cache.stats()["misses"] == 2


def test_geo_hash_and_hos_bucket():
    from backend.cache import geo_hash, hos_bucket

    assert geo_hash("Phoenix") == "city:phoenix"
    assert geo_hash({"lat": 39.96, "lon": -82.99, "city": "Columbus, OH"}) == "ll:40.0,-83.0"
    assert geo_hash("") == "unknown"
    assert hos_bucket(4.5) == "4.5" and hos_bucket(4.6) == "4.5"  # 0.5hr buckets
    assert hos_bucket(None) == "none"


def test_hos_batch_matches_single():
    from backend.agents.wellness_copilot import _evaluate_hos, evaluate_hos_batch

    vals = [0.5, 1.5, 3.0, 5.0, 8.0]
    assert evaluate_hos_batch(vals) == [_evaluate_hos(v) for v in vals]
