# backend/main.py
import asyncio
import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from backend.events import emit, get_queue, cleanup
from backend.graph import graph, VocalCoordState
from backend.models import ToolCallPayload, ToolCallResponse
from backend.tools.j1939 import parse_fault_code, lookup_fault

load_dotenv(dotenv_path="backend/.env")

app = FastAPI(title="Elmeeda VocalCoord")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGINS", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


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
async def tool_call_webhook(payload: ToolCallPayload):
    params = payload.parameters

    # Resolve fault severity from code
    fault_code = params.get("fault_code", "SPN 0 FMI 0")
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
    await emit(payload.conversation_id, {
        "type": "fault_detected",
        "data": {
            "code": fault_code,
            "severity": "red" if severity == "red_stop" else "yellow" if severity == "yellow_caution" else "advisory",
            "description": fault["description"] if fault else "Fault detected"
        }
    })

    initial_state = VocalCoordState(
        conversation_id=payload.conversation_id,
        tool_name=payload.tool_name,
        fault_code=fault_code,
        fault_severity=severity,
        driver_location=params.get("driver_location", {"lat": 39.96, "lon": -82.99, "city": "Columbus, OH"}),
        hos_hours_remaining=float(params.get("hos_hours_remaining", 8.0)),
        load_number=params.get("load_number", "LOAD-0000"),
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

    await emit(payload.conversation_id, {
        "type": "voice_reply_ready",
        "data": {"text": result["voice_reply"]}
    })

    return ToolCallResponse(result=result["voice_reply"])
