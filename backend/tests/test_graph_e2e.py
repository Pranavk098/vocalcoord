"""End-to-end LangGraph test — exercises orchestrator + response nodes together via
graph.ainvoke, not just the individual unit functions. Uses a fault code whose four
agents all resolve, so this runs through the real template-first synthesis path with
no LLM call and no API key required."""
import pytest

from backend.graph import VocalCoordState, graph


@pytest.mark.asyncio
async def test_graph_ainvoke_end_to_end_template_path():
    state = VocalCoordState(
        conversation_id="e2e_test_conv",
        trace_id="trace_e2e",
        t0=0.0,
        tool_name="trigger_fault_response",
        fault_code="SPN 4334 FMI 18",
        fault_severity="red_stop",
        driver_location={"lat": 39.96, "lon": -82.99, "city": "Columbus, OH"},
        hos_hours_remaining=4.5,
        load_number="LOAD-E2E",
        intent="",
        active_agents=[],
        shop_results=[],
        best_shop=None,
        warranty_findings=None,
        wellness_response="",
        dispatch_payload=None,
        voice_reply="",
    )
    result = await graph.ainvoke(state)

    assert result["intent"] == "fault_detected"
    assert set(result["active_agents"]) == {"shop_caller", "warranty_scout", "wellness_copilot", "dispatch_relay"}
    assert result["best_shop"] is not None
    assert result["dispatch_payload"] is not None
    assert result["dispatch_payload"]["simulated"] is True
    assert result["wellness_response"]
    assert result["voice_reply"]
    assert result["voice_reply"].strip().endswith("?")
