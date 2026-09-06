# backend/latency.py
"""Latency budgets + enforcement for the webhook hot path (2nd-cycle revamp).

Budgets (ms) — env-overridable, defaults per the revamp spec:
  parse <50 | branches <400 p95 | synthesize template <10 / LLM <2000
  | SSE first-byte <600 | full turn <2500 (outer webhook guard).

Enforcement is always degrade-never-fail: a branch that exceeds its budget
returns its cached/default partial flagged {"degraded": True, ...} so the turn
still synthesizes. See graph.fault_branch and main.tool_call_webhook.
"""
import asyncio
import logging
import os
from time import perf_counter

log = logging.getLogger("elmeeda")


def _env_ms(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


BUDGETS_MS: dict[str, float] = {
    "parse": _env_ms("BUDGET_PARSE_MS", 50.0),
    "branches": _env_ms("BUDGET_BRANCHES_MS", 400.0),
    "branch_each": _env_ms("BUDGET_BRANCH_EACH_MS", 350.0),
    "synthesize_template": _env_ms("BUDGET_SYNTH_TEMPLATE_MS", 10.0),
    "synthesize_llm": _env_ms("BUDGET_SYNTH_LLM_MS", 2000.0),
    "sse_first_byte": _env_ms("BUDGET_SSE_FIRST_BYTE_MS", 600.0),
    "turn": _env_ms("BUDGET_TURN_MS", 2500.0),
}


async def run_with_budget(coro, *, budget_ms: float, fallback: dict, label: str) -> dict:
    """Await coro with a timeout; on timeout/failure return fallback (degraded).

    Never raises — the turn must survive any single slow branch.
    """
    try:
        return await asyncio.wait_for(coro, timeout=budget_ms / 1000.0)
    except asyncio.TimeoutError:
        log.warning("budget exceeded: %s > %.0fms — degrading", label, budget_ms)
        return {**fallback, "degraded": True, "degraded_reason": f"timeout>{budget_ms:.0f}ms"}
    except Exception as e:  # noqa: BLE001 — branch crash degrades like a timeout
        log.warning("branch failed: %s (%s) — degrading", label, e)
        return {**fallback, "degraded": True, "degraded_reason": str(e)[:200]}


class StageTimer:
    """Sync/async stage stopwatch. Accumulates into a shared dict for the
    eval script's per-stage breakdown (scripts/eval_latency.py)."""

    def __init__(self, store: dict, name: str):
        self._store = store
        self._name = name
        self._t0 = 0.0

    def __enter__(self):
        self._t0 = perf_counter()
        return self

    def __exit__(self, *exc):
        self._store[self._name] = round((perf_counter() - self._t0) * 1000, 2)
        return False

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, *exc):
        return self.__exit__(*exc)
