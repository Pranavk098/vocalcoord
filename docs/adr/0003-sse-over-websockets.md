# 0003. Server-Sent Events over WebSockets for the Mission Control stream

## Status

Accepted

## Context

The Mission Control dashboard needs to show the agent pipeline firing in
real time: fault detected, orchestrator routing decision, each agent
completing, voice reply ready. All of this traffic flows one direction —
backend to frontend. The frontend never needs to push data back over the
same channel; driver input arrives separately, through the ElevenLabs
webhook.

`backend/main.py` exposes this as `GET /events/{conversation_id}` using
`sse-starlette`'s `EventSourceResponse`, backed by a per-conversation
`asyncio.Queue` (`backend/events.py`).

## Decision

Use Server-Sent Events, not WebSockets, for the event stream.

The traffic pattern is unidirectional server→client, which is exactly what
SSE is for. SSE runs over plain HTTP, so it survives the proxies and load
balancers this will eventually sit behind without special upgrade handling,
and browsers reconnect dropped SSE connections automatically — no manual
reconnect/backoff logic needed on the frontend. The server side is also
simpler: an async generator yielding dicts, versus managing a WebSocket
connection lifecycle.

## Consequences

- If a future feature needs client→server real-time push (e.g. driver
  interrupting mid-reply over the same channel), SSE can't carry it — that
  would need a second channel or a switch to WebSockets.
- SSE is text-only (JSON-encoded here), which is a non-issue for this event
  payload shape but would matter if binary streaming were ever needed.
- Each open dashboard holds one long-lived HTTP connection and one
  `asyncio.Queue` per conversation; `cleanup()` in `backend/events.py` exists
  to bound that, and the 30-second ping/timeout loop in the generator keeps
  idle connections alive through proxies that time out silent connections.
