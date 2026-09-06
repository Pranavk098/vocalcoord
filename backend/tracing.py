# backend/tracing.py
"""Stamps every SSE event with a trace_id (ties one fault event to its webhook call,
its agent runs, and its LLM call across log lines) and elapsed_ms (per-stage timing,
rendered as a waterfall in Mission Control and exported the same way to OTel later).
Also fans every event out to the audit trail (backend/audit_log.py) so the exact
sequence of what happened and what was said is replayable.

Hot-path ordering (2nd-cycle revamp): the in-memory SSE queue put is sub-0.1ms
while the SQLite audit commit is ~1-7ms, so the queue is always fed FIRST —
SSE first-byte never waits on disk. The audit write is offloaded with
asyncio.to_thread so four parallel branches don't serialize on the event loop;
callers still await it, so by the time the webhook returns every event is
durable and GET /audit/{trace_id} sees the full trail (no test race).
"""
import asyncio
from time import monotonic

from backend import audit_log, events


def new_trace_id() -> str:
    import secrets
    return secrets.token_hex(8)


async def emit_traced(conversation_id: str, trace_id: str, t0: float, event_type: str, data: dict) -> None:
    elapsed_ms = round((monotonic() - t0) * 1000, 1)
    event = {"type": event_type, "trace_id": trace_id, "elapsed_ms": elapsed_ms, "data": data}
    # Fast path first: unblock SSE subscribers before touching disk.
    await events.emit(conversation_id, event)
    # Slow path off-loop: SQLite commit in a worker thread. Awaited (so the
    # webhook's audit trail is complete on return) but never blocks sibling
    # branches sharing the event loop.
    await asyncio.to_thread(audit_log.record, conversation_id, trace_id, event_type, data)
