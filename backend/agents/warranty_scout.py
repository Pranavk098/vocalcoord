from backend.providers import get_warranty_provider
from backend.tools.j1939 import lookup_fault, parse_fault_code
from backend.tracing import emit_traced


async def run_warranty_scout(state: dict) -> dict:
    conv_id, trace_id, t0 = state["conversation_id"], state["trace_id"], state["t0"]
    provider = get_warranty_provider()

    await emit_traced(conv_id, trace_id, t0, "agent_start", {
        "agent": "warranty_scout", "message": "Checking warranty coverage for detected fault...",
    })

    parsed = parse_fault_code(state.get("fault_code"))
    fault = lookup_fault(parsed[0]) if parsed else None

    findings = None
    if fault and fault.get("warranty_code"):
        await emit_traced(conv_id, trace_id, t0, "agent_tool_call", {
            "agent": "warranty_scout", "tool": "lookup_warranty", "args": {"code": fault["warranty_code"]},
        })
        findings = await provider.lookup(fault["warranty_code"])

    if findings:
        await emit_traced(conv_id, trace_id, t0, "agent_result", {
            "agent": "warranty_scout",
            "summary": f"{findings['part']} covered — {findings['coverage']}",
            "value": f"${findings['claim_value']} claim",
        })
    else:
        await emit_traced(conv_id, trace_id, t0, "agent_result", {
            "agent": "warranty_scout", "summary": "No warranty coverage found for this fault",
        })

    await emit_traced(conv_id, trace_id, t0, "agent_complete", {"agent": "warranty_scout"})

    return {"warranty_findings": findings}
