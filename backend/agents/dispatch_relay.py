from backend.providers import get_dispatch_provider
from backend.tracing import emit_traced


async def run_dispatch_relay(state: dict) -> dict:
    conv_id, trace_id, t0 = state["conversation_id"], state["trace_id"], state["t0"]
    provider = get_dispatch_provider()
    load = state.get("load_number", "LOAD-0000")

    await emit_traced(conv_id, trace_id, t0, "agent_start", {
        "agent": "dispatch_relay", "message": f"Preparing delay notification for {load}...",
    })

    delay = 4 if state.get("fault_severity") == "red_stop" else 2

    await emit_traced(conv_id, trace_id, t0, "agent_tool_call", {
        "agent": "dispatch_relay", "tool": "post_dispatch_webhook",
        "args": {"load_number": load, "delay_hours": delay},
        "simulated": getattr(provider, "simulated", False),
    })

    payload = await provider.notify(load_number=load, delay_hours=delay, reason="Unscheduled mechanical repair")

    await emit_traced(conv_id, trace_id, t0, "agent_result", {
        "agent": "dispatch_relay",
        "summary": f"{load} — dispatch notified, +{delay}hr delay",
        "simulated": payload.get("simulated", False),
    })
    await emit_traced(conv_id, trace_id, t0, "agent_complete", {"agent": "dispatch_relay"})

    return {"dispatch_payload": payload}
