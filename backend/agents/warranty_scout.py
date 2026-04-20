# backend/agents/warranty_scout.py
from backend.tools.j1939 import parse_fault_code, lookup_fault
from backend.tools.warranty_db import lookup_warranty
from backend.events import emit


async def run_warranty_scout(state: dict) -> dict:
    conv_id = state["conversation_id"]

    await emit(conv_id, {
        "type": "agent_start",
        "data": {"agent": "warranty_scout", "message": "Checking warranty coverage for detected fault..."}
    })

    spn, _ = parse_fault_code(state["fault_code"])
    fault = lookup_fault(spn)

    findings = None
    if fault and fault.get("warranty_code"):
        await emit(conv_id, {
            "type": "agent_tool_call",
            "data": {"agent": "warranty_scout", "tool": "lookup_warranty", "args": {"code": fault["warranty_code"]}}
        })
        findings = lookup_warranty(fault["warranty_code"])

    if findings:
        await emit(conv_id, {
            "type": "agent_result",
            "data": {
                "agent": "warranty_scout",
                "summary": f"{findings['part']} covered — {findings['coverage']}",
                "value": f"${findings['claim_value']} claim"
            }
        })
    else:
        await emit(conv_id, {
            "type": "agent_result",
            "data": {"agent": "warranty_scout", "summary": "No warranty coverage found for this fault"}
        })

    await emit(conv_id, {"type": "agent_complete", "data": {"agent": "warranty_scout"}})

    return {"warranty_findings": findings}
