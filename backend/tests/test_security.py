"""HMAC webhook verification (P0-2). Uses a fake Request duck-type since we're testing
the verification function in isolation, not the full FastAPI stack."""
import hashlib
import hmac

import pytest
from fastapi import HTTPException

from backend import security


class _FakeRequest:
    def __init__(self, body: bytes, headers: dict):
        self._body = body
        self.headers = headers

    async def body(self):
        return self._body


@pytest.mark.asyncio
async def test_valid_signature_passes(monkeypatch):
    monkeypatch.setattr(security, "WEBHOOK_SECRET", "testsecret")
    monkeypatch.setattr(security, "DEMO_MODE", False)
    body = b'{"foo": "bar"}'
    sig = hmac.new(b"testsecret", body, hashlib.sha256).hexdigest()
    result = await security.verify_elevenlabs_webhook(_FakeRequest(body, {"elevenlabs-signature": sig}))
    assert result == body


@pytest.mark.asyncio
async def test_invalid_signature_rejected(monkeypatch):
    monkeypatch.setattr(security, "WEBHOOK_SECRET", "testsecret")
    monkeypatch.setattr(security, "DEMO_MODE", False)
    with pytest.raises(HTTPException) as exc:
        await security.verify_elevenlabs_webhook(_FakeRequest(b'{"foo": "bar"}', {"elevenlabs-signature": "wrong"}))
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_missing_signature_rejected_outside_demo_mode(monkeypatch):
    monkeypatch.setattr(security, "WEBHOOK_SECRET", "testsecret")
    monkeypatch.setattr(security, "DEMO_MODE", False)
    with pytest.raises(HTTPException) as exc:
        await security.verify_elevenlabs_webhook(_FakeRequest(b"{}", {}))
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_missing_signature_allowed_in_demo_mode(monkeypatch):
    monkeypatch.setattr(security, "WEBHOOK_SECRET", "testsecret")
    monkeypatch.setattr(security, "DEMO_MODE", True)
    body = b"{}"
    result = await security.verify_elevenlabs_webhook(_FakeRequest(body, {}))
    assert result == body


@pytest.mark.asyncio
async def test_wrong_signature_rejected_even_in_demo_mode(monkeypatch):
    monkeypatch.setattr(security, "WEBHOOK_SECRET", "testsecret")
    monkeypatch.setattr(security, "DEMO_MODE", True)
    with pytest.raises(HTTPException) as exc:
        await security.verify_elevenlabs_webhook(_FakeRequest(b"{}", {"elevenlabs-signature": "wrong"}))
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_oversized_body_rejected(monkeypatch):
    monkeypatch.setattr(security, "MAX_WEBHOOK_BODY_BYTES", 10)
    with pytest.raises(HTTPException) as exc:
        await security.verify_elevenlabs_webhook(_FakeRequest(b"x" * 100, {}))
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_unconfigured_secret_rejected_outside_demo_mode(monkeypatch):
    monkeypatch.setattr(security, "WEBHOOK_SECRET", "")
    monkeypatch.setattr(security, "DEMO_MODE", False)
    with pytest.raises(HTTPException) as exc:
        await security.verify_elevenlabs_webhook(_FakeRequest(b"{}", {}))
    assert exc.value.status_code == 503
