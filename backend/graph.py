# backend/graph.py
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END


class VocalCoordState(TypedDict):
    conversation_id: str
    tool_name: str
    fault_code: str
    fault_severity: str
    driver_location: dict
    hos_hours_remaining: float
    load_number: str
    intent: str
    active_agents: list[str]
    shop_results: list[dict]
    best_shop: Optional[dict]
    warranty_findings: Optional[dict]
    wellness_response: str
    dispatch_payload: Optional[dict]
    voice_reply: str


async def orchestrator_node(state: VocalCoordState) -> VocalCoordState:
    from backend.agents.orchestrator import orchestrate
    result = await orchestrate(dict(state))
    return VocalCoordState(**result)


async def response_node(state: VocalCoordState) -> VocalCoordState:
    from backend.agents.response import build_voice_reply
    voice_reply = await build_voice_reply(dict(state))
    return {**state, "voice_reply": voice_reply}


def build_graph():
    builder = StateGraph(VocalCoordState)
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("response", response_node)
    builder.set_entry_point("orchestrator")
    builder.add_edge("orchestrator", "response")
    builder.add_edge("response", END)
    return builder.compile()


graph = build_graph()
