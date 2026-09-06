# backend/main.py
import asyncio
import json
import logging
import os
from pathlib import Path
from time import monotonic, time

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sse_starlette.sse import EventSourceResponse

from backend import audit_log
from backend.config import (
    CORS_ORIGINS,
    DEMO_MODE,
    OLLAMA_MODEL,
    PROVIDER_LLM,
    PROVIDER_TTS,
    REPLY_CACHE_TTL_SECONDS,
    STT_MODEL,
    STT_MAX_WAV_BYTES,
)
from backend.events import get_queue, queue_count, subscribe, unsubscribe
from backend.geocode import default_location, geocode_city
from backend.graph import VocalCoordState, graph
from backend.models import FaultParameters, ToolCallResponse
from backend.security import verify_elevenlabs_webhook
from backend.sessions import CapacityError, registry
from backend.tools.j1939 import lookup_fault, parse_fault_code
from backend.tracing import emit_traced, new_trace_id

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("elmeeda")

app = FastAPI(title="Elmeeda VocalCoord")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

_INVALID_FAULT_STRINGS = {"", "no fault code provided", "unknown", "none", "n/a"}
_INVALID_LOC_STRINGS = {"", "no location provided", "unknown", "none", "n/a"}

# (reply, expires_at) — TTL'd so ElevenLabs re-trigger guard doesn't grow forever
_reply_cache: dict[str, tuple[str, float]] = {}


def _cache_get(key: str) -> str | None:
    entry = _reply_cache.get(key)
    if entry is None:
        return None
    reply, expires_at = entry
    if time() > expires_at:
        _reply_cache.pop(key, None)
        return None
    return reply


def _cache_set(key: str, reply: str) -> None:
    _reply_cache[key] = (reply, time() + REPLY_CACHE_TTL_SECONDS)


@app.get("/health")
async def health():
    checks = {"anthropic_key_present": bool(os.getenv("ANTHROPIC_API_KEY"))}
    try:
        checks["fixtures_loaded"] = lookup_fault(4334) is not None
    except Exception as e:
        checks["fixtures_loaded"] = False
        checks["fixtures_error"] = str(e)
    checks["demo_mode"] = DEMO_MODE
    checks["active_queues"] = queue_count()
    # HYBRID ownership flags — informational, never gate health status alone.
    checks["provider_llm"] = PROVIDER_LLM
    checks["provider_tts"] = PROVIDER_TTS
    checks["stt_model"] = STT_MODEL
    checks["ollama_model"] = OLLAMA_MODEL
    ok = checks["anthropic_key_present"] and checks["fixtures_loaded"]
    return {"status": "ok" if ok else "degraded", "checks": checks}


@app.get("/voice/provider")
async def voice_provider():
    """Which STT/LLM/TTS backends are active (HYBRID flags)."""
    return {"stt": "faster-whisper", "stt_model": STT_MODEL, "llm": PROVIDER_LLM, "tts": PROVIDER_TTS}


@app.post("/stt")
async def stt_endpoint(
    file: UploadFile = File(...),
    conversation_id: str = Form(default="stt-anon"),
    language: str = Form(default="en"),
):
    """Owned STT: 16 kHz WAV -> transcript (Faster-Whisper small.en, VAD-gated).

    Every stage emits to the existing trace_id audit trail (stt_received,
    stt_vad, stt_complete with stt_ms + rolling p50/p95), so STT latency is
    queryable per trace via GET /audit/{trace_id} exactly like agent timing.
    ElevenLabs TTS path is untouched — see PROVIDER_TTS flag.
    """
    from backend import stt as stt_mod

    t0 = monotonic()
    trace_id = new_trace_id()
    wav_bytes = await file.read()
    if len(wav_bytes) > STT_MAX_WAV_BYTES:
        raise HTTPException(status_code=413, detail="WAV too large")
    await emit_traced(conversation_id, trace_id, t0, "stt_received", {
        "filename": file.filename, "bytes": len(wav_bytes),
    })
    try:
        out = await stt_mod.transcribe_wav(wav_bytes, language=language or "en")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    await emit_traced(conversation_id, trace_id, t0, "stt_vad", out["vad"])
    metrics = stt_mod.get_metrics()
    await emit_traced(conversation_id, trace_id, t0, "stt_complete", {
        "text": out["text"], "language": out["language"],
        "stt_ms": out["stt_ms"], "p50_ms": metrics["p50_ms"], "p95_ms": metrics["p95_ms"],
    })
    return {"trace_id": trace_id, **out, "metrics": metrics}


@app.get("/audit/{trace_id}")
async def audit_trail(trace_id: str):
    """Full replay of one fault event: every SSE event emitted and the exact text
    spoken, in order. This is the audit trail a fleet buyer or a contested-HOS-violation
    review would ask for (see docs/UPGRADE_LOG.md)."""
    return {"trace_id": trace_id, "events": audit_log.history_for_trace(trace_id)}


@app.post("/session/register")
async def register_session(body: dict):
    stream_id = body.get("stream_id") or body.get("conversationId")
    if not stream_id:
        raise HTTPException(status_code=400, detail="stream_id required")
    try:
        token = registry.register(stream_id)
    except CapacityError:
        raise HTTPException(status_code=503, detail="Session capacity reached, try again shortly")
    _reply_cache.pop(stream_id, None)
    log.info("SESSION REGISTERED stream_id=%s", stream_id)
    return {"ok": True, "token": token, "stream_id": stream_id}


@app.get("/events/{conversation_id}")
async def event_stream(conversation_id: str, token: str = ""):
    if not registry.verify(conversation_id, token):
        raise HTTPException(status_code=403, detail="Invalid or expired session token")

    queue = get_queue(conversation_id)
    subscribe(conversation_id)

    async def generator():
        idle_pings = 0
        max_idle_pings = 40  # ~20 min at 30s/ping before we self-terminate the stream
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    idle_pings = 0
                    if event is None:
                        break
                    yield {"data": json.dumps(event)}
                except asyncio.TimeoutError:
                    idle_pings += 1
                    if idle_pings >= max_idle_pings:
                        yield {"data": json.dumps({"type": "session_end", "data": {"reason": "idle_timeout"}})}
                        break
                    yield {"data": json.dumps({"type": "ping"})}
        finally:
            unsubscribe(conversation_id)

    return EventSourceResponse(generator())


def _resolve_fault(raw_fault: str) -> tuple[str, bool, str, dict | None]:
    """Returns (fault_code_used, fault_resolved, severity, fault_record)."""
    if raw_fault.lower() in _INVALID_FAULT_STRINGS:
        if DEMO_MODE:
            demo_code = "SPN 4334 FMI 18"
            spn, _ = parse_fault_code(demo_code)
            fault = lookup_fault(spn)
            return demo_code, True, fault.get("severity", "advisory"), fault
        return raw_fault, False, "advisory", None

    parsed = parse_fault_code(raw_fault)
    if not parsed:
        # Driver said something that isn't a recognizable SPN/FMI code — never guess.
        return raw_fault, False, "advisory", None

    fault = lookup_fault(parsed[0])
    if not fault:
        return raw_fault, False, "advisory", None

    return raw_fault, True, fault.get("severity", "advisory"), fault


def _resolve_location(raw_loc) -> dict:
    if isinstance(raw_loc, dict):
        return raw_loc
    if isinstance(raw_loc, str) and raw_loc.lower() not in _INVALID_LOC_STRINGS:
        geo = geocode_city(raw_loc)
        if geo:
            return geo
        return {"lat": None, "lon": None, "city": raw_loc}
    if DEMO_MODE:
        return default_location()
    return {"lat": None, "lon": None, "city": "unknown"}


@app.post("/webhook/tool-call", response_model=ToolCallResponse)
async def tool_call_webhook(request: Request):
    t0 = monotonic()
    body = await verify_elevenlabs_webhook(request)

    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        log.error("Invalid JSON from ElevenLabs: %s", e)
        return ToolCallResponse(result="Unable to process request.")

    # ElevenLabs sends parameters flat at the top level (not nested under "parameters")
    nested = data.get("parameters", {})
    raw_params = {**nested, **{k: v for k, v in data.items() if k not in ("parameters", "tool_name", "tool_call_id", "type")}}
    tool_name = data.get("tool_name", "trigger_fault_response")

    try:
        params = FaultParameters(**{k: v for k, v in raw_params.items() if k in FaultParameters.model_fields})
    except ValidationError as e:
        log.warning("Invalid tool-call parameters, dropping bad fields and retrying with safe defaults: %s", e)
        raw_hos = raw_params.get("hos_hours_remaining")
        safe = {k: v for k, v in raw_params.items() if k in ("fault_code", "driver_location", "load_number")}
        if isinstance(raw_hos, (int, float)) and 0 <= raw_hos <= 11:
            safe["hos_hours_remaining"] = raw_hos
        try:
            params = FaultParameters(**safe)
        except ValidationError:
            # A non-HOS field was also malformed (e.g. a non-string/dict driver_location) —
            # fall all the way back to defaults rather than risk a second crash.
            params = FaultParameters()

    conversation_id = raw_params.get("stream_id") or data.get("conversation_id") or "unknown"
    trace_id = new_trace_id()

    # PII-light log line: no raw location/load at INFO (see backend/audit_log.py for
    # the full, queryable record of what was actually said).
    log.info(
        "trace_id=%s conversation_id=%s tool_name=%s has_fault_code=%s",
        trace_id, conversation_id, tool_name, bool(raw_params.get("fault_code")),
    )

    # --- Second turn: driver answered the nav yes/no question. Real graph turn
    # through the nav_confirm branch — never the cached fault reply, never a
    # fault re-run. Thread_id = conversation keeps MemorySaver history per driver.
    if tool_name == "confirm_nav_yes_no":
        nav_state = VocalCoordState(
            conversation_id=conversation_id,
            trace_id=trace_id,
            t0=t0,
            tool_name=tool_name,
            fault_code=str(raw_params.get("fault_code") or ""),
            fault_severity="advisory",
            driver_location=_resolve_location(raw_params.get("driver_location", "")),
            hos_hours_remaining=8.0,
            load_number=str(raw_params.get("load_number") or "FRT-28470"),
            intent="",
            active_agents=[],
            shop_results=[],
            best_shop=None,
            warranty_findings=None,
            wellness_response="",
            dispatch_payload=None,
            voice_reply="",
            parameters={k: v for k, v in raw_params.items()},
            destination=str(raw_params.get("destination") or raw_params.get("shop_name") or ""),
        )
        result = await graph.ainvoke(nav_state, config={"configurable": {"thread_id": conversation_id}})
        await emit_traced(conversation_id, trace_id, t0, "voice_reply_ready", {"text": result["voice_reply"]})
        _cache_set(conversation_id, result["voice_reply"])
        return ToolCallResponse(result=result["voice_reply"])

    try:
        params = FaultParameters(**{k: v for k, v in raw_params.items() if k in FaultParameters.model_fields})
    except ValidationError as e:
        log.warning("Invalid tool-call parameters, dropping bad fields and retrying with safe defaults: %s", e)
        raw_hos = raw_params.get("hos_hours_remaining")
        safe = {k: v for k, v in raw_params.items() if k in ("fault_code", "driver_location", "load_number")}
        if isinstance(raw_hos, (int, float)) and 0 <= raw_hos <= 11:
            safe["hos_hours_remaining"] = raw_hos
        try:
            params = FaultParameters(**safe)
        except ValidationError:
            # A non-HOS field was also malformed (e.g. a non-string/dict driver_location) —
            # fall all the way back to defaults rather than risk a second crash.
            params = FaultParameters()

    cached = _cache_get(conversation_id)
    if cached:
        log.info("trace_id=%s Returning cached reply for %s — ignoring re-trigger", trace_id, conversation_id)
        return ToolCallResponse(result=cached)

    fault_code, fault_resolved, severity, fault = _resolve_fault(params.fault_code)

    await emit_traced(conversation_id, trace_id, t0, "fault_detected", {
        "code": fault_code,
        "severity": "red" if severity == "red_stop" else "yellow" if severity == "yellow_caution" else "advisory",
        "description": fault["description"] if fault else "Fault detected",
        "resolved": fault_resolved,
    })

    if not fault_resolved:
        reply = "I didn't catch a valid fault code — can you read me the number off the dash? It usually looks like S-P-N followed by some digits."
        await emit_traced(conversation_id, trace_id, t0, "voice_reply_ready", {"text": reply})
        _cache_set(conversation_id, reply)
        return ToolCallResponse(result=reply)

    driver_location = _resolve_location(params.driver_location)

    initial_state = VocalCoordState(
        conversation_id=conversation_id,
        trace_id=trace_id,
        t0=t0,
        tool_name=tool_name,
        fault_code=fault_code,
        fault_severity=severity,
        driver_location=driver_location,
        hos_hours_remaining=params.hos_hours_remaining,
        load_number=params.load_number,
        intent="",
        active_agents=[],
        shop_results=[],
        best_shop=None,
        warranty_findings=None,
        wellness_response="",
        dispatch_payload=None,
        voice_reply="",
        parameters={k: v for k, v in raw_params.items()},
    )

    result = await graph.ainvoke(initial_state, config={"configurable": {"thread_id": conversation_id}})

    await emit_traced(conversation_id, trace_id, t0, "voice_reply_ready", {"text": result["voice_reply"]})

    _cache_set(conversation_id, result["voice_reply"])
    return ToolCallResponse(result=result["voice_reply"])
