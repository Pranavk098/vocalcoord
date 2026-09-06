"""Behavioral property tests for voice reply synthesis — a lightweight eval harness in
the spirit of AgentSpec (see docs/adr/). Instead of string-matching one hardcoded
transcript, these assert invariants that must hold across the whole (fault_code, hos,
location, load) space: never omit an HOS warning below the 2-hour SEVERE/CRITICAL
threshold, never claim warranty coverage without a matching fixture policy, always end
with a driver confirmation question. All cases here resolve through the template-first
path, so no ANTHROPIC_API_KEY is required."""
import pytest

from backend.agents.orchestrator import orchestrate
from backend.agents.response import build_voice_reply
from backend.tools.j1939 import lookup_fault, parse_fault_code

_ALL_FAULT_CODES = ["SPN 4334 FMI 18", "SPN 3251 FMI 16", "SPN 100 FMI 1", "SPN 521 FMI 9", "SPN 94 FMI 1"]
_NO_WARRANTY_FAULT_CODES = ["SPN 3251 FMI 16", "SPN 94 FMI 1"]  # warranty_code is null in the fixture


async def _run(fault_code: str, hos: float) -> str:
    spn, _ = parse_fault_code(fault_code)
    fault = lookup_fault(spn)
    state = {
        "conversation_id": f"eval_{fault_code}_{hos}",
        "trace_id": "eval_trace",
        "t0": 0.0,
        "tool_name": "trigger_fault_response",
        "fault_code": fault_code,
        "fault_severity": fault.get("severity", "advisory") if fault else "advisory",
        "driver_location": {"lat": 39.96, "lon": -82.99, "city": "Columbus, OH"},
        "hos_hours_remaining": hos,
        "load_number": "LOAD-EVAL",
    }
    state = await orchestrate(state)
    return await build_voice_reply(state)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault_code", _ALL_FAULT_CODES)
@pytest.mark.parametrize("hos", [0.5, 2.0, 8.0])
async def test_reply_always_ends_with_confirmation_question(fault_code, hos):
    reply = await _run(fault_code, hos)
    assert reply.strip().endswith("?")


@pytest.mark.asyncio
@pytest.mark.parametrize("fault_code", _ALL_FAULT_CODES)
@pytest.mark.parametrize("hos", [0.0, 0.99, 1.0, 1.99])  # CRITICAL and SEVERE tiers
async def test_hos_warning_never_omitted_below_severe_threshold(fault_code, hos):
    reply = await _run(fault_code, hos)
    assert "HOS" in reply


@pytest.mark.asyncio
@pytest.mark.parametrize("fault_code", _NO_WARRANTY_FAULT_CODES)
async def test_no_warranty_claim_without_matching_policy(fault_code):
    reply = await _run(fault_code, 8.0)
    assert "is covered under" not in reply
    assert "No warranty coverage" in reply


@pytest.mark.asyncio
async def test_warranty_claim_present_when_policy_matches():
    reply = await _run("SPN 4334 FMI 18", 8.0)  # warranty_code = EPA_EMISSION_COVERAGE
    assert "is covered under" in reply
