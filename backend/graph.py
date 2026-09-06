# backend/graph.py
"""VocalCoord LangGraph: branched per intent with retry + checkpointing.

Nodes (one per ROUTING_MAP intent + synthesis):
  router -> fault_branch | wellness_branch | warranty_branch | dispatch_branch
          | shop_branch | nav_confirm_branch -> synthesize (-> synthesize_retry) -> END

- router classifies tool_name -> intent (backend/agents/orchestrator.py).
- Each *_branch node runs exactly the agents ROUTING_MAP[intent] lists.
- synthesize is template-first (no LLM on the common path); OOD states go
  through the owned LLM path (Ollama local with Anthropic fallback).
- synthesize_retry is the retry/safety net around LLM synthesis: if synthesize
  left no reply (LLM outage mid-flight), it retries once more, then renders
  the degraded template so the driver never gets dead air.
- Compiled with a MemorySaver checkpointer; callers pass
  config={"configurable": {"thread_id": conversation_id}}. A thin wrapper
  injects a default thread_id so existing graph.ainvoke(state) calls (tests,
  evals) keep working without changes.

Diagram: docs/architecture.mmd (mermaid source of truth) + docs/architecture.png
rendered via scripts/render_graph.py (PNG when mermaid-ink is reachable).
"""
from typing import Optional
from typing_extensions import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph


class _RequiredState(TypedDict):
    conversation_id: str
    trace_id: str
    t0: float
    tool_name: str
    fault_code: str
    fault_severity: str
    driver_location: dict
    hos_hours_remaining: float
    load_number: str
    intent: str
    active_agents: list[str]
    shop_results: list[dict]
    best_shop: Optional[dict]
    warranty_findings: Optional[dict]
    wellness_response: str
    dispatch_payload: Optional[dict]
    voice_reply: str


class VocalCoordState(_RequiredState, total=False):
    parameters: dict
    synthesis_attempts: int
    synthesis_error: str
    reply_source: str
    destination: str
    nav_confirmed: Optional[bool]


async def router_node(state: dict) -> dict:
    from backend.agents.orchestrator import ROUTING_MAP, classify_intent
    from backend.tracing import emit_traced

    intent = classify_intent(state.get("tool_name", ""), state.get("parameters", {}))
    agents = ROUTING_MAP[intent]
    await emit_traced(
        state["conversation_id"], state["trace_id"], state["t0"],
        "orchestrator", {"intent": intent, "routing_to": agents},
    )
    return {**state, "intent": intent, "active_agents": agents}


def _route_by_intent(state: dict) -> str:
    intent = state.get("intent") or "fault_detected"
    return {
        "fault_detected": "fault_branch",
        "wellness_check": "wellness_branch",
        "warranty_query": "warranty_branch",
        "dispatch_update": "dispatch_branch",
        "shop_search": "shop_branch",
        "nav_confirm": "nav_confirm_branch",
    }.get(intent, "fault_branch")


async def fault_branch(state: dict) -> dict:
    """Four agents fan out concurrently, each capped by its own budget.

    - Per-branch asyncio.wait_for (BUDGETS_MS["branch_each"], default 350ms):
      a hung branch returns its degraded fallback instead of stalling the turn.
    - Early-partial SSE: each runner already streams agent_result as soon as
      IT finishes (see shop_caller/warranty_scout/...); here we additionally
      emit branch_partial as each future lands so Mission Control can paint
      progress without waiting for the slowest branch.
    - Never raises: slow/crashed branch -> cached/default partial flagged
      degraded=True, synthesize still runs on whatever resolved.
    """
    import asyncio

    from backend.agents.dispatch_relay import run_dispatch_relay
    from backend.agents.shop_caller import run_shop_caller
    from backend.agents.warranty_scout import run_warranty_scout
    from backend.agents.wellness_copilot import run_wellness_copilot
    from backend.latency import BUDGETS_MS, run_with_budget
    from backend.tracing import emit_traced

    budget = BUDGETS_MS["branch_each"]
    runners = (
        ("shop_caller", run_shop_caller(state),
         {"shop_results": [], "best_shop": None}),
        ("warranty_scout", run_warranty_scout(state),
         {"warranty_findings": None}),
        ("wellness_copilot", run_wellness_copilot(state),
         {"wellness_response": "[CLEAR] HOS status temporarily unavailable — confirm with dispatch."}),
        ("dispatch_relay", run_dispatch_relay(state),
         {"dispatch_payload": {"load_number": state.get("load_number", "LOAD-0000"),
                               "status": "PENDING", "delay_estimate_hours": 2,
                               "reason": "Unscheduled mechanical repair",
                               "notified": False, "simulated": True}}),
    )
    pending = {
        asyncio.ensure_future(
            run_with_budget(coro, budget_ms=budget, fallback=fb, label=name)
        ): name
        for name, coro, fb in runners
    }
    merged = dict(state)
    degraded_branches: list[str] = []
    while pending:
        done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for fut in done:
            name = pending.pop(fut)
            result = fut.result()  # run_with_budget never raises
            if result.get("degraded"):
                degraded_branches.append(name)
            merged.update({k: v for k, v in result.items() if k != "degraded"})
            await emit_traced(
                state["conversation_id"], state["trace_id"], state["t0"],
                "branch_partial",
                {"branch": name, "degraded": bool(result.get("degraded")),
                 "remaining": sorted(pending[v] for v in pending)},
            )
    if degraded_branches:
        merged["_degraded_branches"] = degraded_branches
    return merged


async def wellness_branch(state: dict) -> dict:
    from backend.agents.wellness_copilot import run_wellness_copilot

    return {**state, **await run_wellness_copilot(state)}


async def warranty_branch(state: dict) -> dict:
    from backend.agents.warranty_scout import run_warranty_scout

    return {**state, **await run_warranty_scout(state)}


async def dispatch_branch(state: dict) -> dict:
    from backend.agents.dispatch_relay import run_dispatch_relay

    return {**state, **await run_dispatch_relay(state)}


async def shop_branch(state: dict) -> dict:
    from backend.agents.shop_caller import run_shop_caller

    return {**state, **await run_shop_caller(state)}


async def nav_confirm_branch(state: dict) -> dict:
    """Second turn: driver answered yes/no. No agents re-run."""
    from backend.agents.nav_confirm import parse_confirmation, render_nav_reply
    from backend.tracing import emit_traced

    confirmed = parse_confirmation(state.get("parameters", {}) or {})
    reply = render_nav_reply(confirmed, state)
    await emit_traced(
        state["conversation_id"], state["trace_id"], state["t0"],
        "nav_confirmed",
        {"confirmed": confirmed, "destination": state.get("destination") or (state.get("best_shop") or {}).get("name")},
    )
    return {
        **state,
        "nav_confirmed": confirmed,
        "voice_reply": reply,
        "reply_source": "template:nav_confirm",
        "synthesis_attempts": 0,
        "synthesis_error": "",
    }


async def synthesize_node(state: dict) -> dict:
    """Template-first synthesis; OOD states go through the owned LLM path."""
    # nav_confirm already rendered its reply — pass through untouched.
    if state.get("intent") == "nav_confirm" and state.get("voice_reply"):
        return dict(state)
    from backend.agents.response import build_voice_reply_with_meta
    from backend.tracing import emit_traced

    try:
        reply, source = await build_voice_reply_with_meta(dict(state))
        await emit_traced(
            state["conversation_id"], state["trace_id"], state["t0"],
            "synthesis", {"source": source, "attempts": 1},
        )
        return {**state, "voice_reply": reply, "reply_source": source,
                "synthesis_attempts": 1, "synthesis_error": ""}
    except Exception as e:  # noqa: BLE001 — retry node converts this to degraded reply
        return {**state, "voice_reply": "", "reply_source": "",
                "synthesis_attempts": 1, "synthesis_error": str(e)}


async def synthesize_retry_node(state: dict) -> dict:
    """Retry/safety net around LLM synthesis: one more attempt, then degraded."""
    if state.get("voice_reply"):
        return dict(state)
    from backend.agents.response import (
        _findings_block,
        _render_degraded_template,
    )
    from backend.llm import llm_synthesize
    from backend.tracing import emit_traced

    attempts = int(state.get("synthesis_attempts") or 1) + 1
    try:
        text, backend_used = await llm_synthesize(_findings_block(state))
        await emit_traced(
            state["conversation_id"], state["trace_id"], state["t0"],
            "synthesis_retry", {"source": f"llm:{backend_used}", "attempts": attempts},
        )
        return {**state, "voice_reply": text, "reply_source": f"llm:{backend_used}",
                "synthesis_attempts": attempts, "synthesis_error": ""}
    except Exception as e:  # noqa: BLE001 — degraded template, never dead air
        reply = _render_degraded_template(state)
        await emit_traced(
            state["conversation_id"], state["trace_id"], state["t0"],
            "synthesis_retry", {"source": "degraded", "attempts": attempts, "error": str(e)},
        )
        return {**state, "voice_reply": reply, "reply_source": "degraded",
                "synthesis_attempts": attempts, "synthesis_error": str(e)}


def _needs_retry(state: dict) -> str:
    if state.get("intent") == "nav_confirm":
        return END
    if not state.get("voice_reply") or state.get("synthesis_error"):
        return "synthesize_retry"
    return END


def build_graph():
    builder = StateGraph(VocalCoordState)
    builder.add_node("router", router_node)
    builder.add_node("fault_branch", fault_branch)
    builder.add_node("wellness_branch", wellness_branch)
    builder.add_node("warranty_branch", warranty_branch)
    builder.add_node("dispatch_branch", dispatch_branch)
    builder.add_node("shop_branch", shop_branch)
    builder.add_node("nav_confirm_branch", nav_confirm_branch)
    builder.add_node("synthesize", synthesize_node)
    builder.add_node("synthesize_retry", synthesize_retry_node)

    builder.set_entry_point("router")
    builder.add_conditional_edges("router", _route_by_intent, {
        "fault_branch": "fault_branch",
        "wellness_branch": "wellness_branch",
        "warranty_branch": "warranty_branch",
        "dispatch_branch": "dispatch_branch",
        "shop_branch": "shop_branch",
        "nav_confirm_branch": "nav_confirm_branch",
    })
    for branch in ("fault_branch", "wellness_branch", "warranty_branch", "dispatch_branch", "shop_branch"):
        builder.add_edge(branch, "synthesize")
    builder.add_edge("nav_confirm_branch", END)
    builder.add_conditional_edges("synthesize", _needs_retry, {
        "synthesize_retry": "synthesize_retry",
        END: END,
    })
    builder.add_edge("synthesize_retry", END)
    return builder.compile(checkpointer=MemorySaver())


_compiled = build_graph()


class _GraphWrapper:
    """Delegates to the compiled graph, defaulting thread_id for bare ainvoke calls."""

    def __init__(self, inner):
        self._inner = inner

    def _with_defaults(self, config: dict | None, state: dict | None = None) -> dict:
        cfg = dict(config or {})
        configurable = dict(cfg.get("configurable") or {})
        if "thread_id" not in configurable:
            fallback = None
            if isinstance(state, dict):
                fallback = state.get("conversation_id") or state.get("trace_id")
            configurable["thread_id"] = fallback or "default"
        cfg["configurable"] = configurable
        return cfg

    async def ainvoke(self, state: dict, config: dict | None = None, **kwargs):
        return await self._inner.ainvoke(state, self._with_defaults(config, state), **kwargs)

    def __getattr__(self, name):
        return getattr(self._inner, name)


graph = _GraphWrapper(_compiled)

# Backwards-compatible node names (pre-branch graph exposed these).
async def orchestrator_node(state: VocalCoordState) -> VocalCoordState:
    out = await router_node(dict(state))
    branch = _route_by_intent(out)
    runner = {
        "fault_branch": fault_branch,
        "wellness_branch": wellness_branch,
        "warranty_branch": warranty_branch,
        "dispatch_branch": dispatch_branch,
        "shop_branch": shop_branch,
        "nav_confirm_branch": nav_confirm_branch,
    }[branch]
    merged = await runner(out)
    return VocalCoordState(**{**out, **merged})


async def response_node(state: VocalCoordState) -> VocalCoordState:
    out = await synthesize_node(dict(state))
    if not out.get("voice_reply"):
        out = await synthesize_retry_node(out)
    return {**state, **out}
