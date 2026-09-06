import asyncio

from backend.agents.dispatch_relay import run_dispatch_relay
from backend.agents.shop_caller import run_shop_caller
from backend.agents.warranty_scout import run_warranty_scout
from backend.agents.wellness_copilot import run_wellness_copilot
from backend.tracing import emit_traced

ROUTING_MAP: dict[str, list[str]] = {
    "fault_detected":  ["shop_caller", "warranty_scout", "wellness_copilot", "dispatch_relay"],
    "wellness_check":  ["wellness_copilot"],
    "warranty_query":  ["warranty_scout"],
    "dispatch_update": ["dispatch_relay"],
    "shop_search":     ["shop_caller"],
    # Multi-turn nav confirmation: driver answering "yes/no" to the fault reply's
    # closing question is a real second tool call (confirm_nav_yes_no), not a
    # re-trigger of the fault flow. No agents re-run; the graph's nav_confirm
    # branch renders the follow-up reply directly from confirmation state.
    "nav_confirm":     [],
}

_AGENT_RUNNERS = {
    "shop_caller":      run_shop_caller,
    "warranty_scout":   run_warranty_scout,
    "wellness_copilot": run_wellness_copilot,
    "dispatch_relay":   run_dispatch_relay,
}


def classify_intent(tool_name: str, parameters: dict) -> str:
    mapping = {
        "trigger_fault_response": "fault_detected",
        "request_wellness_check": "wellness_check",
        "query_warranty":         "warranty_query",
        "update_dispatch":        "dispatch_update",
        "shop_search":            "shop_search",
        "confirm_nav_yes_no":     "nav_confirm",
    }
    return mapping.get(tool_name, "fault_detected")


async def orchestrate(state: dict) -> dict:
    conv_id, trace_id, t0 = state["conversation_id"], state["trace_id"], state["t0"]
    intent = classify_intent(state["tool_name"], state.get("parameters", {}))
    agents = ROUTING_MAP[intent]

    state["intent"] = intent
    state["active_agents"] = agents

    await emit_traced(conv_id, trace_id, t0, "orchestrator", {"intent": intent, "routing_to": agents})

    tasks = [_AGENT_RUNNERS[agent](state) for agent in agents]
    results = await asyncio.gather(*tasks)

    for result in results:
        state.update(result)

    return state
