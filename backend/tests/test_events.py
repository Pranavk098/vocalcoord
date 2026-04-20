# backend/tests/test_events.py
import asyncio
import pytest
from backend.events import get_queue, emit, cleanup


@pytest.mark.asyncio
async def test_emit_puts_event_on_queue():
    conv_id = "test_conv_001"
    cleanup(conv_id)

    await emit(conv_id, {"type": "ping", "data": {}})

    queue = get_queue(conv_id)
    event = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event == {"type": "ping", "data": {}}
    cleanup(conv_id)


@pytest.mark.asyncio
async def test_same_conversation_id_gets_same_queue():
    conv_id = "test_conv_002"
    cleanup(conv_id)

    q1 = get_queue(conv_id)
    q2 = get_queue(conv_id)
    assert q1 is q2
    cleanup(conv_id)
