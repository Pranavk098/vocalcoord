# backend/agents/shop_caller.py
from backend.tools.j1939 import parse_fault_code, lookup_fault
from backend.tools.shop_db import search_shops, get_best_shop
from backend.events import emit


async def run_shop_caller(state: dict) -> dict:
    conv_id = state["conversation_id"]

    await emit(conv_id, {
        "type": "agent_start",
        "data": {"agent": "shop_caller", "message": f"Searching certified shops near {state['driver_location']['city']}..."}
    })

    spn, _ = parse_fault_code(state["fault_code"])
    fault = lookup_fault(spn)
    needs_def_pump = fault is not None and fault.get("likely_part") == "DEF Pump Assembly"

    await emit(conv_id, {
        "type": "agent_tool_call",
        "data": {"agent": "shop_caller", "tool": "search_shops", "args": {"radius_miles": 25, "needs_def_pump": needs_def_pump}}
    })

    shops = search_shops(needs_def_pump=needs_def_pump, max_distance=25)
    best = get_best_shop(shops, needs_def_pump=needs_def_pump)

    if best:
        await emit(conv_id, {
            "type": "agent_result",
            "data": {
                "agent": "shop_caller",
                "summary": f"{best['name']} — {best['open_bay_time']}, {best['distance_miles']}mi",
                "value": f"${best['labor_rate']}/hr"
            }
        })
    await emit(conv_id, {"type": "agent_complete", "data": {"agent": "shop_caller"}})

    return {"shop_results": shops, "best_shop": best}
