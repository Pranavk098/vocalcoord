# 0005. HYBRID: owned STT + LLM, ElevenLabs TTS retained, owned orchestrator + evals

## Status

Accepted

## Context

VocalCoord shipped fully hosted: ElevenLabs for STT+TTS, Anthropic for every
OOD reply, one linear orchestrator -> response graph. That is correct for a
demo and wrong for a deployable fleet product: per-minute voice costs scale
with fleet size, audio + fault data leaves our boundary on every turn, and the
two-node graph (ADR 0001's "revisit if it doesn't grow branches" clause) never
grew the branching, retry, or checkpointing ADR 0001 promised.

The HYBRID choice: own STT + LLM (the cost/latency/data-boundary wins), keep
ElevenLabs TTS (voice quality is the demo's moat and Piper parity isn't
there), own the orchestrator + evals (branching, retries, checkpoints, latency
proof).

## Decision

1. **Real LangGraph** (`backend/graph.py`): router + one branch node per
   `ROUTING_MAP` intent (fault/wellness/warranty/dispatch/shop/nav_confirm),
   `synthesize` + `synthesize_retry` around LLM synthesis, `MemorySaver`
   checkpointer keyed by conversation. Diagram source of truth is
   `docs/architecture.mmd`, PNG at `docs/architecture.png` (rendered by
   `scripts/render_graph.py`; `.mmd` is the fallback when mermaid-ink is
   unreachable).
2. **Owned STT** (`backend/stt.py`, `POST /stt`): Faster-Whisper `small.en` on
   16 kHz WAV, Silero VAD with energy fallback, per-request `stt_ms` + rolling
   p50/p95 logged and emitted to the existing `trace_id` audit trail
   (`stt_received/vad/complete`). Missing `faster-whisper` install 503s with
   an install hint; tests inject a fake transcriber.
3. **Owned LLM** (`backend/llm.py`): `PROVIDER_LLM=local` tries Ollama
   `qwen2.5:3b` first with Anthropic fallback; `anthropic` (default) preserves
   current behavior. Template-first stays the fast path — the LLM only sees
   OOD states, unchanged from ADR 0004.
4. **TTS untouched**: `PROVIDER_TTS=elevenlabs` (default) is the current path;
   `piper` reserves the owned route without changing any ElevenLabs behavior.
5. **Multi-turn nav** (`confirm_nav_yes_no`, `backend/agents/nav_confirm.py`):
   the fault reply's closing yes/no is a real second tool call through the
   `nav_confirm` branch — no agents re-run, no cached fault reply returned.
   Frontend holds the session open until the nav turn lands (see `HomeClient`).
6. **Latency eval** (`scripts/eval_latency.py`): 20 scripted fault utterances,
   webhook-to-reply p50/p95 + template-hit rate + HOS-tier table, published to
   README.

## Consequences

- STT/LLM inference moves inside our deploy boundary (docker-compose adds
   `stt`/`ollama` services when enabled); ElevenLabs remains the voice UX.
- `faster-whisper` (ctranslate2) is intentionally commented out of
   `requirements.txt` — install where STT runs, not in minimal CI images.
- Ollama quality for OOD phrasing is unproven vs Sonnet; the Anthropic
   fallback + degraded template bound the blast radius, and evals stay
   template-path so CI never depends on either backend.
- Frontend no longer auto-ends on the first reply; a dropped nav turn now
   surfaces as a pending confirmation instead of a silent session end.
