# backend/tracing.py
"""Stamps every SSE event with a trace_id (ties one fault event to its webhook call,
its agent runs, and its LLM call across log lines) and elapsed_ms (per-stage timing,
rendered as a waterfall in Mission Control and exported the same way to OTel later).
Also fans every event out to the audit trail (backend/audit_log.py) so the exact
sequence of what happened and what was said is replayable.
"""
from time import monotonic

from backend import audit_log, events


def new_trace_id() -> str:
    import secrets
    return secrets.token_hex(8)


async def emit_traced(conversation_id: str, trace_id: str, t0: float, event_type: str, data: dict) -> None:
    elapsed_ms = round((monotonic() - t0) * 1000, 1)
    event = {"type": event_type, "trace_id": trace_id, "elapsed_ms": elapsed_ms, "data": data}
    await events.emit(conversation_id, event)
    audit_log.record(conversation_id, trace_id, event_type, data)
