# backend/agents/orchestrator.py
import asyncio
from backend.agents.shop_caller import run_shop_caller
from backend.agents.warranty_scout import run_warranty_scout
from backend.agents.wellness_copilot import run_wellness_copilot
from backend.agents.dispatch_relay import run_dispatch_relay
from backend.events import emit

ROUTING_MAP: dict[str, list[str]] = {
    "fault_detected":  ["shop_caller", "warranty_scout", "wellness_copilot", "dispatch_relay"],
    "wellness_check":  ["wellness_copilot"],
    "warranty_query":  ["warranty_scout"],
    "dispatch_update": ["dispatch_relay"],
    "shop_search":     ["shop_caller"],
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
    }
    return mapping.get(tool_name, "fault_detected")


async def orchestrate(state: dict) -> dict:
    conv_id = state["conversation_id"]
    intent = classify_intent(state["tool_name"], state.get("parameters", {}))
    agents = ROUTING_MAP[intent]

    state["intent"] = intent
    state["active_agents"] = agents

    await emit(conv_id, {
        "type": "orchestrator",
        "data": {"intent": intent, "routing_to": agents}
    })

    tasks = [_AGENT_RUNNERS[agent](state) for agent in agents]
    results = await asyncio.gather(*tasks)

    for result in results:
        state.update(result)

    return state
