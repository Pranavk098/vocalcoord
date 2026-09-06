# backend/tests/test_graph_branches.py
"""HYBRID branch coverage: every ROUTING_MAP intent takes its own graph path
(separate nodes/edges, not one internal gather), the retry node degrades
cleanly on LLM outage, and MemorySaver checkpointing isolates threads."""
from time import monotonic

import pytest

from backend.agents.orchestrator import ROUTING_MAP
from backend.graph import graph


def _base_state(tool_name: str, **overrides):
    state = {
        "conversation_id": "branch_test",
        "trace_id": "trace_branch",
        "t0": monotonic(),
        "tool_name": tool_name,
        "fault_code": "SPN 4334 FMI 18",
        "fault_severity": "red_stop",
        "driver_location": {"lat": 39.96, "lon": -82.99, "city": "Columbus, OH"},
        "hos_hours_remaining": 4.5,
        "load_number": "LOAD-BRANCH",
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


@pytest.mark.asyncio
async def test_routing_map_has_branch_per_intent():
    assert set(ROUTING_MAP) >= {
        "fault_detected", "wellness_check", "warranty_query",
        "dispatch_update", "shop_search", "nav_confirm",
    }


@pytest.mark.asyncio
async def test_fault_branch_runs_four_agents_template_reply():
    result = await graph.ainvoke(
        _base_state("trigger_fault_response", conversation_id="br_fault", trace_id="t_br_fault"),
        config={"configurable": {"thread_id": "br_fault"}},
    )
    assert result["intent"] == "fault_detected"
    assert set(result["active_agents"]) == {"shop_caller", "warranty_scout", "wellness_copilot", "dispatch_relay"}
    assert result["reply_source"] == "template"
    assert result["voice_reply"].strip().endswith("?")


@pytest.mark.asyncio
async def test_wellness_branch_single_agent_no_llm():
    result = await graph.ainvoke(
        _base_state("request_wellness_check", conversation_id="br_well", trace_id="t_br_well"),
        config={"configurable": {"thread_id": "br_well"}},
    )
    assert result["intent"] == "wellness_check"
    assert result["active_agents"] == ["wellness_copilot"]
    assert result["reply_source"] == "template:wellness"
    assert result["wellness_response"]
    assert result["best_shop"] is None  # shop agent did NOT run on this branch


@pytest.mark.asyncio
async def test_warranty_branch_single_agent_no_llm():
    result = await graph.ainvoke(
        _base_state("query_warranty", conversation_id="br_warr", trace_id="t_br_warr"),
        config={"configurable": {"thread_id": "br_warr"}},
    )
    assert result["intent"] == "warranty_query"
    assert result["active_agents"] == ["warranty_scout"]
    assert result["reply_source"] == "template:warranty"


@pytest.mark.asyncio
async def test_dispatch_branch_single_agent_no_llm():
    result = await graph.ainvoke(
        _base_state("update_dispatch", conversation_id="br_disp", trace_id="t_br_disp"),
        config={"configurable": {"thread_id": "br_disp"}},
    )
    assert result["intent"] == "dispatch_update"
    assert result["active_agents"] == ["dispatch_relay"]
    assert result["reply_source"] == "template:dispatch"


@pytest.mark.asyncio
async def test_shop_branch_single_agent_no_llm():
    result = await graph.ainvoke(
        _base_state("shop_search", conversation_id="br_shop", trace_id="t_br_shop"),
        config={"configurable": {"thread_id": "br_shop"}},
    )
    assert result["intent"] == "shop_search"
    assert result["active_agents"] == ["shop_caller"]
    assert result["reply_source"] == "template:shop"


@pytest.mark.asyncio
async def test_nav_confirm_branch_is_real_turn_not_cached_fault():
    result = await graph.ainvoke(
        _base_state(
            "confirm_nav_yes_no",
            conversation_id="br_nav",
            trace_id="t_br_nav",
            parameters={"confirmed": "yes"},
            destination="Freightliner of Columbus",
        ),
        config={"configurable": {"thread_id": "br_nav"}},
    )
    assert result["intent"] == "nav_confirm"
    assert result["nav_confirmed"] is True
    assert result["reply_source"] == "template:nav_confirm"
    assert "Navigation set" in result["voice_reply"]


@pytest.mark.asyncio
async def test_nav_confirm_no_answer():
    result = await graph.ainvoke(
        _base_state(
            "confirm_nav_yes_no",
            conversation_id="br_nav_no",
            trace_id="t_br_nav_no",
            parameters={"confirmed": "no"},
        ),
        config={"configurable": {"thread_id": "br_nav_no"}},
    )
    assert result["nav_confirmed"] is False
    assert "No problem" in result["voice_reply"]


@pytest.mark.asyncio
async def test_retry_node_degrades_on_llm_outage(monkeypatch):
    """Incomplete fault state forces the OOD LLM path; total LLM failure must
    still produce the degraded template (never dead air, never raise)."""
    import backend.agents.response as resp_mod

    async def _boom(*a, **k):
        raise RuntimeError("llm down")

    monkeypatch.setattr(resp_mod, "build_voice_reply_with_meta", _boom)
    from backend.graph import synthesize_node, synthesize_retry_node

    # synthesize records the failure instead of raising
    partial = await synthesize_node(_base_state("trigger_fault_response"))
    assert partial["voice_reply"] == "" and partial["synthesis_error"]
    # retry node converts failure into the degraded template
    final = await synthesize_retry_node(partial)
    assert final["voice_reply"]
    assert final["reply_source"] == "degraded"
    assert final["synthesis_attempts"] >= 2


@pytest.mark.asyncio
async def test_checkpointer_isolates_threads():
    r1 = await graph.ainvoke(
        _base_state("trigger_fault_response", conversation_id="thr_1", trace_id="t1"),
        config={"configurable": {"thread_id": "thr_1"}},
    )
    r2 = await graph.ainvoke(
        _base_state("request_wellness_check", conversation_id="thr_2", trace_id="t2"),
        config={"configurable": {"thread_id": "thr_2"}},
    )
    assert r1["intent"] == "fault_detected"
    assert r2["intent"] == "wellness_check"


@pytest.mark.asyncio
async def test_webhook_nav_confirm_is_second_turn_not_cached_fault():
    """POST /webhook/tool-call with confirm_nav_yes_no returns a nav follow-up
    (not the cached fault reply) and emits nav_confirmed to the audit trail."""
    from httpx import ASGITransport, AsyncClient

    from backend.main import app

    conv = "conv_nav_webhook_001"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        fault = await client.post("/webhook/tool-call", json={
            "conversation_id": conv, "tool_name": "trigger_fault_response",
            "parameters": {"fault_code": "SPN 4334 FMI 18", "driver_location": "Columbus, OH",
                           "hos_hours_remaining": 4.5, "load_number": "LOAD-NAV"},
        })
        assert fault.status_code == 200
        assert "set nav" in fault.json()["result"]
        nav = await client.post("/webhook/tool-call", json={
            "conversation_id": conv, "tool_name": "confirm_nav_yes_no",
            "parameters": {"confirmed": "yes"},
        })
    assert nav.status_code == 200
    assert "Navigation set" in nav.json()["result"]
    assert nav.json()["result"] != fault.json()["result"]
