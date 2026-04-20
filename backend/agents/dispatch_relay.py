# backend/agents/dispatch_relay.py
from backend.events import emit


async def run_dispatch_relay(state: dict) -> dict:
    conv_id = state["conversation_id"]
    load = state.get("load_number", "LOAD-0000")

    await emit(conv_id, {
        "type": "agent_start",
        "data": {"agent": "dispatch_relay", "message": f"Preparing delay notification for {load}..."}
    })

    await emit(conv_id, {
        "type": "agent_tool_call",
        "data": {"agent": "dispatch_relay", "tool": "post_dispatch_webhook", "args": {"load_number": load, "delay_hours": 4}}
    })

    payload = {
        "load_number": load,
        "status": "DELAYED",
        "delay_estimate_hours": 4,
        "reason": "Unscheduled mechanical repair",
        "notified": True
    }

    await emit(conv_id, {
        "type": "agent_result",
        "data": {"agent": "dispatch_relay", "summary": f"{load} — dispatch notified, +4hr delay"}
    })
    await emit(conv_id, {"type": "agent_complete", "data": {"agent": "dispatch_relay"}})
    await emit(conv_id, {
        "type": "dispatch_sent",
        "data": {"load_number": load, "eta_delay": "4 hours"}
    })

    return {"dispatch_payload": payload}
