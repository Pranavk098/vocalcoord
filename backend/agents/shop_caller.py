from backend.providers import get_shop_provider
from backend.tools.j1939 import lookup_fault, parse_fault_code
from backend.tracing import emit_traced


async def run_shop_caller(state: dict) -> dict:
    conv_id, trace_id, t0 = state["conversation_id"], state["trace_id"], state["t0"]
    provider = get_shop_provider()

    await emit_traced(conv_id, trace_id, t0, "agent_start", {
        "agent": "shop_caller",
        "message": f"Searching certified shops near {state['driver_location'].get('city', 'your location')}...",
    })

    parsed = parse_fault_code(state.get("fault_code"))
    fault = lookup_fault(parsed[0]) if parsed else None
    needs_def_pump = fault is not None and fault.get("likely_part") == "DEF Pump Assembly"

    await emit_traced(conv_id, trace_id, t0, "agent_tool_call", {
        "agent": "shop_caller", "tool": "search_shops",
        "args": {"radius_miles": 25, "needs_def_pump": needs_def_pump},
    })

    shops = await provider.search(needs_def_pump=needs_def_pump, max_distance=25)
    best = await provider.best(shops, needs_def_pump=needs_def_pump, hos_hours_remaining=state.get("hos_hours_remaining"))

    if best:
        await emit_traced(conv_id, trace_id, t0, "agent_result", {
            "agent": "shop_caller",
            "summary": f"{best['name']} — {best['open_bay_time']}, {best['distance_miles']}mi",
            "value": f"${best['labor_rate']}/hr",
        })
    else:
        await emit_traced(conv_id, trace_id, t0, "agent_result", {
            "agent": "shop_caller", "summary": "No certified shop found within 25 miles",
        })
    await emit_traced(conv_id, trace_id, t0, "agent_complete", {"agent": "shop_caller"})

    return {"shop_results": shops, "best_shop": best}
