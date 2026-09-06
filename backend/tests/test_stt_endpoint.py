# backend/tests/test_stt_endpoint.py
"""Owned STT endpoint: 16 kHz WAV in, transcript + VAD + trace_id audit out.

faster-whisper is NOT required in CI — tests inject a fake transcriber via
backend.stt.set_transcriber_for_tests. A missing native dependency must 503
with an install hint, never 500."""
import io
import wave

import pytest
from httpx import ASGITransport, AsyncClient

from backend import stt as stt_mod
from backend.main import app


def _wav_bytes(sr: int = 16000, seconds: float = 0.5, freq: float = 440.0, voiced: bool = True) -> bytes:
    import math
    import struct

    n = int(sr * seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for i in range(n):
            sample = math.sin(2 * math.pi * freq * i / sr) if voiced else 0.0
            wf.writeframes(struct.pack("<h", int(sample * 12000)))
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _fake_transcriber():
    stt_mod.set_transcriber_for_tests(lambda wav, lang="en": {"text": "SPN 4334 FMI 18", "language": "en"})
    stt_mod._LATENCIES_MS.clear()
    yield
    stt_mod.set_transcriber_for_tests(None)
    stt_mod._LATENCIES_MS.clear()


@pytest.mark.asyncio
async def test_stt_returns_transcript_and_audit_trail():
    from backend import audit_log

    wav = _wav_bytes()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/stt",
            files={"file": ("fault16k.wav", wav, "audio/wav")},
            data={"conversation_id": "conv_stt_001"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == "SPN 4334 FMI 18"
    assert body["vad"]["method"] in ("silero", "energy")
    assert body["stt_ms"] >= 0
    assert body["metrics"]["count"] >= 1
    events = audit_log.history_for_trace(body["trace_id"])
    types = [e["type"] for e in events]
    assert "stt_received" in types and "stt_complete" in types


@pytest.mark.asyncio
async def test_stt_rejects_non_16k_wav():
    wav = _wav_bytes(sr=8000)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/stt", files={"file": ("fault8k.wav", wav, "audio/wav")}, data={"conversation_id": "conv_stt_8k"},
        )
    assert resp.status_code == 400
    assert "16k" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_stt_rejects_garbage_bytes():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/stt",
            files={"file": ("bad.wav", b"not a wav at all", "audio/wav")},
            data={"conversation_id": "conv_stt_bad"},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_stt_metrics_accumulate_p50_p95():
    wav = _wav_bytes()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i in range(3):
            resp = await client.post(
                "/stt",
                files={"file": ("f.wav", wav, "audio/wav")},
                data={"conversation_id": f"conv_stt_m{i}"},
            )
            assert resp.status_code == 200
    metrics = stt_mod.get_metrics()
    assert metrics["count"] == 3
    assert metrics["p50_ms"] is not None and metrics["p95_ms"] is not None


@pytest.mark.asyncio
async def test_stt_503_without_model_or_fake(monkeypatch):
    stt_mod.set_transcriber_for_tests(None)
    monkeypatch.setattr(stt_mod, "_get_model", lambda: (_ for _ in ()).throw(RuntimeError("no model")))
    wav = _wav_bytes()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/stt", files={"file": ("f.wav", wav, "audio/wav")}, data={"conversation_id": "conv_stt_503"},
        )
    assert resp.status_code == 503
