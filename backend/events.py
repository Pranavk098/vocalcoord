# backend/events.py
import asyncio
from typing import Dict

_queues: Dict[str, asyncio.Queue] = {}


def get_queue(conversation_id: str) -> asyncio.Queue:
    if conversation_id not in _queues:
        _queues[conversation_id] = asyncio.Queue()
    return _queues[conversation_id]


async def emit(conversation_id: str, event: dict) -> None:
    queue = get_queue(conversation_id)
    await queue.put(event)


def cleanup(conversation_id: str) -> None:
    _queues.pop(conversation_id, None)
