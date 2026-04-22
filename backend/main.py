# backend/main.py
import asyncio
import json
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from backend.events import emit, get_queue, cleanup
from backend.graph import graph, VocalCoordState
from backend.models import ToolCallPayload, ToolCallResponse
from backend.tools.j1939 import parse_fault_code, lookup_fault

load_dotenv(dotenv_path="backend/.env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("elmeeda")

app = FastAPI(title="Elmeeda VocalCoord")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGINS", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Tracks the most recent active frontend session ID
_active_session_id: str | None = None

# Cache completed replies so repeated tool calls (ElevenLabs re-triggers) return instantly
_reply_cache: dict[str, str] = {}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/session/register")
async def register_session(body: dict):
    global _active_session_id
    _active_session_id = body.get("conversationId")
    _reply_cache.pop(_active_session_id, None)  # clear stale cache for fresh session
    log.info("SESSION REGISTERED: %s", _active_session_id)
    return {"ok": True}


@app.get("/events/{conversation_id}")
async def event_stream(conversation_id: str):
    queue = get_queue(conversation_id)

    async def generator():
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                if event is None:
                    break
                yield {"data": json.dumps(event)}
            except asyncio.TimeoutError:
                yield {"data": json.dumps({"type": "ping"})}

    return EventSourceResponse(generator())


@app.post("/webhook/tool-call", response_model=ToolCallResponse)
async def tool_call_webhook(request: Request):
    body = await request.body()
    log.info("WEBHOOK RAW BODY: %s", body.decode())

    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        log.error("Invalid JSON from ElevenLabs: %s", e)
        return ToolCallResponse(result="Unable to process request.")

    log.info("WEBHOOK PARSED: %s", data)

    # ElevenLabs sends parameters flat at the top level (not nested under "parameters")
    nested = data.get("parameters", {})
    params = {**nested, **{k: v for k, v in data.items() if k not in ("parameters", "tool_name", "tool_call_id", "type")}}
    tool_name = data.get("tool_name", "trigger_fault_response")

    # Use the registered frontend session ID — ElevenLabs tool conversation_id
    # uses a different internal ID than the WebSocket session the frontend subscribes to
    conversation_id = _active_session_id or data.get("conversation_id") or params.get("conversation_id") or "unknown"
    log.info("Using conversation_id=%s (registered=%s)", conversation_id, _active_session_id)

    log.info("conversation_id=%s tool_name=%s params=%s", conversation_id, tool_name, params)

    # Return cached reply if agents already ran for this conversation (ElevenLabs re-trigger guard)
    if conversation_id in _reply_cache:
        log.info("Returning cached reply for %s — ignoring re-trigger", conversation_id)
        return ToolCallResponse(result=_reply_cache[conversation_id])

    # Resolve fault code — ignore placeholder strings from the LLM
    raw_fault = params.get("fault_code", "")
    _invalid = {"", "no fault code provided", "unknown", "none", "n/a"}
    fault_code = raw_fault if raw_fault.lower() not in _invalid else "SPN 4334 FMI 18"  # demo default
    severity = "advisory"
    fault = None
    try:
        spn, _ = parse_fault_code(fault_code)
        fault = lookup_fault(spn)
        if fault:
            severity = fault.get("severity", "advisory")
    except Exception:
        pass

    # Emit fault_detected so dashboard lights up before agents start
    await emit(conversation_id, {
        "type": "fault_detected",
        "data": {
            "code": fault_code,
            "severity": "red" if severity == "red_stop" else "yellow" if severity == "yellow_caution" else "advisory",
            "description": fault["description"] if fault else "Fault detected"
        }
    })

    # Resolve driver location — ignore placeholder strings from the LLM
    raw_loc = params.get("driver_location", "")
    _invalid_loc = {"", "no location provided", "unknown", "none", "n/a"}
    if isinstance(raw_loc, dict):
        driver_location = raw_loc
    elif isinstance(raw_loc, str) and raw_loc.lower() not in _invalid_loc:
        driver_location = {"lat": 39.96, "lon": -82.99, "city": raw_loc}
    else:
        driver_location = {"lat": 39.96, "lon": -82.99, "city": "Columbus, OH"}

    initial_state = VocalCoordState(
        conversation_id=conversation_id,
        tool_name=tool_name,
        fault_code=fault_code,
        fault_severity=severity,
        driver_location=driver_location,
        hos_hours_remaining=float(params.get("hos_hours_remaining", 8.0)),
        load_number=params.get("load_number", "FRT-28470"),
        intent="",
        active_agents=[],
        shop_results=[],
        best_shop=None,
        warranty_findings=None,
        wellness_response="",
        dispatch_payload=None,
        voice_reply="",
    )

    result = await graph.ainvoke(initial_state)

    await emit(conversation_id, {
        "type": "voice_reply_ready",
        "data": {"text": result["voice_reply"]}
    })

    _reply_cache[conversation_id] = result["voice_reply"]
    return ToolCallResponse(result=result["voice_reply"])
