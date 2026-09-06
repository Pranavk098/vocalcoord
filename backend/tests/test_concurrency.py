"""Concurrency / multi-tenancy regression test. This is the test that would have
caught P0-1: two drivers hitting the webhook at the same time must never see each
other's fault data. Before the fix, the module-level `_active_session_id` global
meant the second request's registration silently overwrote the first, and both SSE
queues could end up receiving events resolved against the wrong conversation_id."""
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from backend.events import cleanup, get_queue
from backend.main import app


@pytest.mark.asyncio
async def test_concurrent_conversations_do_not_cross_contaminate():
    conv_a, conv_b = "conv_A_concurrency_test", "conv_B_concurrency_test"
    cleanup(conv_a)
    cleanup(conv_b)
    queue_a = get_queue(conv_a)
    queue_b = get_queue(conv_b)

    payload_a = {
        "type": "tool_call", "conversation_id": conv_a, "tool_name": "trigger_fault_response",
        "parameters": {"fault_code": "SPN 4334 FMI 18", "driver_location": "Phoenix", "load_number": "LOAD-A"},
    }
    payload_b = {
        "type": "tool_call", "conversation_id": conv_b, "tool_name": "trigger_fault_response",
        "parameters": {"fault_code": "SPN 100 FMI 1", "driver_location": "Dallas", "load_number": "LOAD-B"},
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp_a, resp_b = await asyncio.gather(
            client.post("/webhook/tool-call", json=payload_a),
            client.post("/webhook/tool-call", json=payload_b),
        )

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200

    events_a, events_b = [], []
    while not queue_a.empty():
        events_a.append(await queue_a.get())
    while not queue_b.empty():
        events_b.append(await queue_b.get())

    faults_a = [e["data"]["code"] for e in events_a if e["type"] == "fault_detected"]
    faults_b = [e["data"]["code"] for e in events_b if e["type"] == "fault_detected"]

    assert faults_a == ["SPN 4334 FMI 18"]
    assert faults_b == ["SPN 100 FMI 1"]
    assert "SPN 100 FMI 1" not in faults_a
    assert "SPN 4334 FMI 18" not in faults_b

    cleanup(conv_a)
    cleanup(conv_b)
