# backend/agents/wellness_copilot.py
from backend.events import emit


async def run_wellness_copilot(state: dict) -> dict:
    conv_id = state["conversation_id"]
    hos = state.get("hos_hours_remaining", 8.0)

    await emit(conv_id, {
        "type": "agent_start",
        "data": {"agent": "wellness_copilot", "message": f"Checking driver status — {hos:.1f}hrs HOS remaining..."}
    })

    await emit(conv_id, {
        "type": "agent_tool_call",
        "data": {"agent": "wellness_copilot", "tool": "check_hos_rules", "args": {"hours_remaining": hos}}
    })

    if hos < 2.0:
        message = f"You're down to {hos:.1f} hours on your HOS. After this stop, you'll need a 10-hour reset."
    elif hos < 4.0:
        message = f"You have {hos:.1f} hours left on your clock. The shop stop will eat about 2 hours — plan accordingly."
    else:
        message = f"You have {hos:.1f} hours remaining. Plenty of time to handle this repair and continue your run."

    await emit(conv_id, {
        "type": "agent_result",
        "data": {"agent": "wellness_copilot", "summary": message}
    })
    await emit(conv_id, {"type": "agent_complete", "data": {"agent": "wellness_copilot"}})

    return {"wellness_response": message}
