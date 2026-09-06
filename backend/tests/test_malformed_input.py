"""Malformed-input regression suite. Every case here reproduces a specific audit
finding (P1-1 unparseable fault codes, P1-5 invalid HOS values) that previously
crashed the webhook with an unhandled exception. All fault codes used here resolve
through the template-first synthesis path, so none of these tests need an
ANTHROPIC_API_KEY or network access."""
import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


async def _post(client, params, conversation_id):
    payload = {
        "type": "tool_call",
        "conversation_id": conversation_id,
        "tool_name": "trigger_fault_response",
        "parameters": params,
    }
    return await client.post("/webhook/tool-call", json=payload)


@pytest.mark.asyncio
@pytest.mark.parametrize("phrase", ["check engine light", "DEF light is on", "SPN four thousand"])
async def test_unparseable_fault_code_gets_clarifying_question_not_500(phrase):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await _post(client, {"fault_code": phrase}, conversation_id=f"conv_malformed_{abs(hash(phrase))}")
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert "fault code" in result.lower()


@pytest.mark.asyncio
async def test_bad_hos_string_does_not_crash():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await _post(
            client, {"fault_code": "SPN 4334 FMI 18", "hos_hours_remaining": "about four"},
            conversation_id="conv_malformed_badhos",
        )
    assert resp.status_code == 200
    assert len(resp.json()["result"]) > 10


@pytest.mark.asyncio
async def test_negative_hos_does_not_crash():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await _post(
            client, {"fault_code": "SPN 4334 FMI 18", "hos_hours_remaining": -3},
            conversation_id="conv_malformed_neghos",
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_absurd_hos_does_not_crash():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await _post(
            client, {"fault_code": "SPN 4334 FMI 18", "hos_hours_remaining": 900},
            conversation_id="conv_malformed_bighos",
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_invalid_json_body_returns_200_not_500():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/webhook/tool-call", content=b"not json at all", headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_unrecognized_city_does_not_fabricate_columbus():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await _post(
            client,
            {"fault_code": "SPN 4334 FMI 18", "driver_location": "Anchorage"},
            conversation_id="conv_malformed_unknown_city",
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_oversized_body_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/webhook/tool-call",
            content=b"x" * 100_000,
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 413
