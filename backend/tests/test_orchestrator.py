# backend/tests/test_orchestrator.py
from backend.agents.orchestrator import classify_intent, ROUTING_MAP


def test_fault_detected_routes_to_four_agents():
    intent = classify_intent("trigger_fault_response", {})
    assert intent == "fault_detected"
    assert set(ROUTING_MAP[intent]) == {"shop_caller", "warranty_scout", "wellness_copilot", "dispatch_relay"}


def test_wellness_check_routes_to_wellness():
    intent = classify_intent("request_wellness_check", {})
    assert intent == "wellness_check"
    assert ROUTING_MAP[intent] == ["wellness_copilot"]


def test_warranty_query_routes_to_warranty():
    intent = classify_intent("query_warranty", {})
    assert intent == "warranty_query"
    assert ROUTING_MAP[intent] == ["warranty_scout"]


def test_unknown_tool_defaults_to_fault_detected():
    intent = classify_intent("unknown_tool", {})
    assert intent == "fault_detected"
