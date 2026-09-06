# backend/events.py
"""Per-conversation async event queues for the SSE stream.

Bounded via TTL + reference counting: a queue lives as long as it has an active SSE
subscriber, or for QUEUE_TTL_SECONDS past its last activity if nobody ever connected
or everybody disconnected. Previously these dicts grew forever with no eviction and
no reference to "cleanup()" anywhere in the app (P1-4) — combined with the old IDOR
(P0-3, anyone could allocate a queue by GETting any conversation_id) that was a
remotely triggerable memory leak. The IDOR is closed separately in main.py via signed
session tokens; this file bounds memory even for legitimately-registered sessions that
never finish cleanly.
"""
import asyncio
from dataclasses import dataclass, field
from time import monotonic
from typing import Dict

from backend.config import QUEUE_TTL_SECONDS


@dataclass
class _Entry:
    queue: asyncio.Queue
    last_activity: float
    subscribers: int = 0


_queues: Dict[str, _Entry] = {}


def _sweep() -> None:
    now = monotonic()
    expired = [
        cid for cid, e in _queues.items()
        if e.subscribers <= 0 and now - e.last_activity > QUEUE_TTL_SECONDS
    ]
    for cid in expired:
        _queues.pop(cid, None)


def get_queue(conversation_id: str) -> asyncio.Queue:
    _sweep()
    entry = _queues.get(conversation_id)
    if entry is None:
        entry = _Entry(queue=asyncio.Queue(), last_activity=monotonic())
        _queues[conversation_id] = entry
    return entry.queue


def subscribe(conversation_id: str) -> None:
    entry = _queues.get(conversation_id)
    if entry is not None:
        entry.subscribers += 1
        entry.last_activity = monotonic()


def unsubscribe(conversation_id: str) -> None:
    entry = _queues.get(conversation_id)
    if entry is not None:
        entry.subscribers = max(0, entry.subscribers - 1)
        entry.last_activity = monotonic()


async def emit(conversation_id: str, event: dict) -> None:
    queue = get_queue(conversation_id)
    entry = _queues[conversation_id]
    entry.last_activity = monotonic()
    await queue.put(event)


def cleanup(conversation_id: str) -> None:
    _queues.pop(conversation_id, None)


def queue_count() -> int:
    """For health/debug endpoints."""
    return len(_queues)
