# backend/agents/wellness_copilot.py
from backend.tracing import emit_traced

# Federal HOS rules (property-carrying drivers, FMCSA 49 CFR Part 395)
_SHOP_STOP_HOURS = 2.0   # estimated repair time used in margin calculations

_TIERS = [
    # (max_hos, status_label, value_label, summary_fn)
    (
        1.0,
        "CRITICAL",
        "10-HR RESET REQUIRED",
        lambda h: (
            f"HOS CRITICAL — only {h:.1f} hr left on your 11-hour driving limit. "
            "You cannot legally continue after this stop. Dispatch has been notified; "
            "coordinate a reset location with your carrier before leaving the shop."
        ),
    ),
    (
        2.0,
        "SEVERE",
        "RESET AFTER STOP",
        lambda h: (
            f"You have {h:.1f} hrs left, and the repair will take roughly {_SHOP_STOP_HOURS:.0f} hrs. "
            "You'll hit your 11-hour limit at the shop. Plan for a 10-hour reset before resuming — "
            "confirm a safe rest location with dispatch."
        ),
    ),
    (
        3.5,
        "CAUTION",
        f"~{_SHOP_STOP_HOURS:.0f} HRS TO REPAIR",
        lambda h: (
            f"You have {h:.1f} hrs remaining. After the ~{_SHOP_STOP_HOURS:.0f}-hr repair, "
            f"you'll have roughly {h - _SHOP_STOP_HOURS:.1f} hr of drive time left — tight margin. "
            "If you've been on duty 8+ hours without a break, take your 30-minute break before "
            "re-entering traffic."
        ),
    ),
    (
        6.0,
        "WATCH",
        None,
        lambda h: (
            f"You have {h:.1f} hrs on your clock. Plenty for the repair, with "
            f"~{h - _SHOP_STOP_HOURS:.1f} hrs remaining after. "
            "If you're past 8 hrs of continuous driving, plan your mandatory 30-min break "
            "before your next stint."
        ),
    ),
    (
        float("inf"),
        "CLEAR",
        None,
        lambda h: (
            f"You have {h:.1f} hrs remaining — well within your 11-hour limit. "
            f"After the repair you'll still have ~{h - _SHOP_STOP_HOURS:.1f} hrs to run. "
            "HOS is not a constraint here."
        ),
    ),
]


def _evaluate_hos(hos: float) -> tuple[str, str, str | None]:
    """Return (summary, status_label, value_label) for the given HOS hours."""
    for max_h, status, value, summary_fn in _TIERS:
        if hos < max_h:
            return summary_fn(hos), status, value
    # fallback (shouldn't reach here)
    return f"HOS: {hos:.1f} hrs remaining.", "CLEAR", None


def evaluate_hos_batch(hos_values: list[float]) -> list[tuple[str, str, str | None]]:
    """Batch HOS computation: one pass over N clocks, no per-call tracing or
    event-loop hops. Used by evals/sweeps; the single-turn runner below calls
    _evaluate_hos directly (same math, no overhead either way)."""
    return [_evaluate_hos(float(h)) for h in hos_values]


async def run_wellness_copilot(state: dict) -> dict:
    conv_id, trace_id, t0 = state["conversation_id"], state["trace_id"], state["t0"]
    hos = float(state.get("hos_hours_remaining", 8.0))

    await emit_traced(conv_id, trace_id, t0, "agent_start", {
        "agent": "wellness_copilot",
        "message": f"Checking HOS compliance — {hos:.1f} hrs on 11-hr driving limit...",
    })

    await emit_traced(conv_id, trace_id, t0, "agent_tool_call", {
        "agent": "wellness_copilot",
        "tool": "check_hos_rules",
        "args": {"hours_remaining": hos, "estimated_stop_hours": _SHOP_STOP_HOURS},
    })

    summary, status_label, value_label = _evaluate_hos(hos)

    result_data: dict = {
        "agent": "wellness_copilot",
        "summary": summary,
    }
    if value_label:
        result_data["value"] = value_label

    await emit_traced(conv_id, trace_id, t0, "agent_result", result_data)
    await emit_traced(conv_id, trace_id, t0, "agent_complete", {"agent": "wellness_copilot"})

    return {"wellness_response": f"[{status_label}] {summary}"}
