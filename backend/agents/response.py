# backend/agents/response.py
import anthropic

_client = anthropic.Anthropic()


async def build_voice_reply(state: dict) -> str:
    fault_desc = "Vehicle fault detected"
    if state.get("fault_code"):
        from backend.tools.j1939 import parse_fault_code, lookup_fault
        spn, _ = parse_fault_code(state["fault_code"])
        fault = lookup_fault(spn)
        if fault:
            fault_desc = fault["plain_english"]

    context_parts = []

    if state.get("best_shop"):
        shop = state["best_shop"]
        context_parts.append(
            f"Shop booked: {shop['name']}, {shop['distance_miles']} miles ahead, "
            f"open bay at {shop['open_bay_time']}, has required part: {shop.get('has_def_pump', False)}"
        )

    if state.get("warranty_findings"):
        w = state["warranty_findings"]
        context_parts.append(
            f"Warranty: {w['coverage']}, claim value ${w['claim_value']}, "
            f"labor included: {w['labor_included']}"
        )

    if state.get("dispatch_payload"):
        d = state["dispatch_payload"]
        context_parts.append(f"Dispatch notified: {d['load_number']} delayed ~{d['delay_estimate_hours']} hours")

    if state.get("wellness_response"):
        context_parts.append(f"HOS status: {state['wellness_response']}")

    prompt = f"""You are the Elmeeda Co-Pilot voice assistant for a professional truck driver.

Fault: {fault_desc}

Agent findings:
{chr(10).join(f'- {c}' for c in context_parts)}

Write a single voice reply (2-3 sentences max) that:
1. States the fault and urgency clearly
2. Summarizes what was arranged (shop, warranty, dispatch)
3. Ends with a yes/no confirmation question for the driver

Rules: Be direct. No filler. Driver is behind the wheel. Never say "I" or "I've been"."""

    response = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text
