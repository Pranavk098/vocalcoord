# backend/stt.py
"""Owned STT path: Faster-Whisper small.en behind a FastAPI /stt endpoint.

Contract: 16 kHz mono WAV bytes in, transcript + VAD gate + timing out.
VAD-gated with Silero when torch+silero are available, otherwise a dependency-
free energy-based fallback (RMS over 30 ms frames) so CI and CPU-only boxes
still get a real speech/silence gate without a network fetch.

Latency accounting: every transcription records its wall time into an in-memory
ring; get_metrics() exposes count/p50/p95 for the /stt response and for
/scripts/eval_latency.py. Each request also emits stt_* events through the
existing trace_id audit trail (backend/tracing.py emit_traced).
"""
import io
import logging
import statistics
import wave
from collections import deque
from time import monotonic
from typing import Callable, Optional

log = logging.getLogger("elmeeda")

SAMPLE_RATE = 16000

_LATENCIES_MS: deque[float] = deque(maxlen=1000)

_Transcriber = Callable[[bytes, Optional[str]], dict]
_test_transcriber: _Transcriber | None = None

_model = None


def set_transcriber_for_tests(fn: _Transcriber | None) -> None:
    """Inject a fake transcriber (tests) — bypasses faster-whisper import."""
    global _test_transcriber
    _test_transcriber = fn


def record_latency(ms: float) -> None:
    _LATENCIES_MS.append(ms)


def get_metrics() -> dict:
    lat = list(_LATENCIES_MS)
    if not lat:
        return {"count": 0, "p50_ms": None, "p95_ms": None, "mean_ms": None}
    ordered = sorted(lat)
    n = len(ordered)

    def _pct(p: float) -> float:
        # Nearest-rank percentile over the observed window.
        import math

        k = max(1, min(n, math.ceil(p / 100 * n)))
        return round(ordered[k - 1], 1)

    return {
        "count": n,
        "p50_ms": _pct(50),
        "p95_ms": _pct(95),
        "mean_ms": round(statistics.fmean(lat), 1),
    }


def decode_wav_16k(wav_bytes: bytes) -> tuple["object", int]:
    """Decode WAV bytes -> (mono float32 numpy array, sample_rate).

    Raises ValueError on non-WAV input or sample-rate mismatch (contract is 16k).
    """
    import numpy as np

    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            sr = wf.getframerate()
            nch = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            frames = wf.readframes(wf.getnframes())
    except wave.Error as e:
        raise ValueError(f"invalid WAV: {e}") from e
    if sr != SAMPLE_RATE:
        raise ValueError(f"expected 16kHz WAV, got {sr}Hz")
    if sampwidth == 2:
        pcm = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 1:
        pcm = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError(f"unsupported sample width: {sampwidth * 8}-bit")
    if nch == 2:
        pcm = pcm.reshape(-1, 2).mean(axis=1).astype(np.float32)
    elif nch != 1:
        raise ValueError(f"unsupported channel count: {nch}")
    return pcm, sr


def vad_gate(pcm, sr: int = SAMPLE_RATE) -> dict:
    """Return {is_speech, speech_ratio, method}. Silero when available, else energy."""
    import numpy as np

    method = "silero"
    try:
        import torch

        # torch.hub fetch needs network on first use; failure falls through to energy.
        model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            trust_repo=True,
        )
        (get_speech_timestamps, _, _, _, _) = utils
        wav = torch.from_numpy(np.asarray(pcm, dtype=np.float32))
        stamps = get_speech_timestamps(wav, model, sampling_rate=sr)
        total_speech = sum(s["end"] - s["start"] for s in stamps)
        ratio = total_speech / max(1, len(pcm))
        return {"is_speech": bool(stamps), "speech_ratio": round(float(ratio), 3), "method": method}
    except Exception as e:
        log.debug("Silero VAD unavailable (%s), using energy fallback", e)
    # Energy fallback: RMS over 30 ms frames, speech if >=15% frames above threshold.
    frame = int(sr * 0.03)
    if len(pcm) < frame:
        return {"is_speech": False, "speech_ratio": 0.0, "method": "energy"}
    import numpy as np

    frames = np.asarray(pcm, dtype=np.float32)
    n = len(frames) // frame
    rms = [float((frames[i * frame : (i + 1) * frame] ** 2).mean() ** 0.5) for i in range(n)]
    thresh = 0.02
    voiced = sum(1 for r in rms if r > thresh)
    ratio = voiced / max(1, n)
    return {"is_speech": ratio >= 0.15, "speech_ratio": round(float(ratio), 3), "method": "energy"}


def _get_model():
    global _model
    if _model is not None:
        return _model
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError(
            "faster-whisper not installed — pip install faster-whisper (see requirements.txt)"
        ) from e
    from backend.config import STT_MODEL

    _model = WhisperModel(STT_MODEL, device="auto", compute_type="auto")
    return _model


async def transcribe_wav(wav_bytes: bytes, language: str | None = "en") -> dict:
    """Full owned STT pass. Returns {text, language, duration_s, vad, stt_ms}."""
    import asyncio

    t0 = monotonic()
    pcm, sr = decode_wav_16k(wav_bytes)
    vad = vad_gate(pcm, sr)
    duration_s = round(len(pcm) / sr, 2)

    if _test_transcriber is not None:
        out = _test_transcriber(wav_bytes, language)
        text = out.get("text", "")
        lang = out.get("language", language or "en")
    else:
        model = _get_model()
        segments, info = await asyncio.to_thread(
            model.transcribe, pcm, language=language, beam_size=1
        )
        text = "".join(s.text for s in segments).strip()
        lang = getattr(info, "language", language or "en")

    stt_ms = round((monotonic() - t0) * 1000, 1)
    record_latency(stt_ms)
    metrics = get_metrics()
    log.info("stt_complete stt_ms=%.1f p50=%s p95=%s vad=%s", stt_ms, metrics["p50_ms"], metrics["p95_ms"], vad)
    return {
        "text": text,
        "language": lang,
        "duration_s": duration_s,
        "vad": vad,
        "stt_ms": stt_ms,
    }
