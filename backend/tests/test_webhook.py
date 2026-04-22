# backend/tests/test_webhook.py
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_tool_call_webhook_returns_voice_reply():
    payload = {
        "type": "tool_call",
        "conversation_id": "test_conv_webhook_001",
        "tool_name": "trigger_fault_response",
        "parameters": {
            "fault_code": "SPN 4334 FMI 18",
            "driver_location": {"lat": 39.96, "lon": -82.99, "city": "Columbus, OH"},
            "hos_hours_remaining": 4.5,
            "load_number": "LOAD-9910"
        }
    }
    mock_reply = "DEF pump is failing — bay booked at Freightliner of Columbus, warranty covers it. Set nav — yes or no?"
    with patch("backend.agents.response.build_voice_reply", new=AsyncMock(return_value=mock_reply)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/webhook/tool-call", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    assert len(data["result"]) > 10  # non-empty voice reply
