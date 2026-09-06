# VocalCoord GTM Upgrade Log

Brief, specific record of decisions made during the audit-driven hardening + feature pass (Aug 2026).
Format per entry: **what** → **why** → **repercussions/tradeoffs**.

---

## Backend hardening

**P0-1 global session ID → keyed registry** (`backend/sessions.py`). Frontend generates its own `stream_id`, registers it, gets a signed token, subscribes to SSE with it. Webhook resolves `conversation_id` per-request (`params.stream_id` → ElevenLabs' own id → "unknown") — no shared mutable state, so no cross-tenant leak. *Repercussion:* full fix (ElevenLabs echoing `stream_id` back in tool params) needs a dashboard-side dynamic variable on the tool schema — can't be done from code. Documented as a manual setup step. Fallback path degrades safely (dead SSE panel, not data leakage) if that step isn't done yet — frontend surfaces this via connection-state UI rather than failing silently.

**P0-2 webhook auth** (`backend/security.py`). HMAC-SHA256 over raw body, 64KB size cap. In `DEMO_MODE` a *missing* signature is allowed (logged loudly) so local/hackathon use isn't blocked before ElevenLabs signing is configured; a *wrong* signature is always rejected regardless of mode. Outside `DEMO_MODE`, missing signature or unset secret is a hard 401/503.

**P0-3 SSE IDOR** (`backend/main.py` `/events/{id}`). Requires `?token=` bound to a registered `stream_id` via the session registry. Closes both the eavesdropping and the unbounded-queue-allocation angle.

**P0-4 sync Anthropic client blocking the event loop** (`backend/agents/response.py`). `AsyncAnthropic`, lazy-constructed (fixes crash-on-import when `ANTHROPIC_API_KEY` unset), `timeout=4s`, `max_retries=1`.

**Template-first synthesis** (`backend/agents/response.py`). When all 4 agents resolve (the common path), render the voice reply from structured state directly — no LLM call. Reserved the LLM for OOD states (no shop found, agent gaps), with a hard-coded degraded template if even that fails, so the driver never gets dead air. *Repercussion:* cuts the dominant latency cost and LLM cost to ~zero on the majority path; verified via `test_response.py` that the template always ends in a confirmation question and never claims warranty coverage without a matching fixture policy.

**P1-1 unparseable fault codes** (`backend/tools/j1939.py`). `parse_fault_code` is now total (regex-based, returns `Optional[tuple]`) instead of raising. `main.py` treats an unresolved fault as a real product state — driver gets "read me the number off the dash" instead of a 500, and the 4-agent fanout is skipped entirely (nothing to look up), saving latency too.

**P1-2 fabrication** (`backend/main.py`, `backend/geocode.py`). Demo-default fault code only kicks in for genuinely empty/placeholder input, gated behind `DEMO_MODE`; garbage input (e.g. "check engine light") never gets silently reassigned to a different real fault. Location: static city→coords lookup table replaces hardcoded Columbus — unrecognized cities keep the driver's stated city string with null coords rather than lying about location. *Repercussion:* shop selection was never actually geo-driven (fixture `distance_miles` is a static field, not computed from coords), so this fixes display honesty, not routing logic — that requires Phase 2 telematics/real geocoding, out of scope here.

**P1-4 unbounded memory** (`backend/events.py`, `backend/main.py` reply cache, `backend/sessions.py`). All three now TTL'd; SSE queues additionally reference-counted by subscriber and self-terminate after ~20 min of idle pings, emitting a `session_end` event.

**P1-5 validation** (`backend/models.py`). `FaultParameters` with `hos_hours_remaining: Field(ge=0, le=11)` — the real FMCSA limit, not an arbitrary bound. On validation failure, retries with bad fields dropped rather than crashing; falls all the way back to defaults if even that fails (belt-and-suspenders — verified in `test_malformed_input.py`).

**P1-6 CORS** — `CORS_ORIGINS` now splits on comma (`backend/config.py`).

**P2-1 fake dispatch tool-call** — `backend/providers.py`'s `FixtureDispatchProvider` marks every result `"simulated": true`, carried into the SSE event payload.

**P2-2 shop ranking ignoring HOS** (`backend/tools/shop_db.py`). Weighted score over distance, bay-wait-vs-HOS-margin, part availability, labor rate — replaces pure nearest-shop sort. Makes the wellness agent's output actually feed the shop agent's decision, which is the four-agent architecture's stated reason to exist. *Repercussion:* bay-wait is a fixed estimate (0h for "Now", 2h otherwise) since there's no real scheduling data and using wall-clock time would make shop ranking nondeterministic across the day — flagged as a fixture limitation, real fix is Phase 1's ShopProvider swap.

**P2-6 logging/tracing** (`backend/tracing.py`, `backend/audit_log.py`). Every SSE event now carries `trace_id` + `elapsed_ms` and is mirrored into a SQLite audit trail (`backend/data/audit_trail.db`, gitignored) — the "what did we say and when" record the audit's liability section asked for, without pulling in Postgres for a demo. INFO-level logs no longer print raw location/load; full detail lives in the audit trail instead.

**Provider interfaces** (`backend/providers.py`, Phase 1 from the audit, done now rather than deferred since every other P1/P2 fix benefits from landing behind the interface once). `ShopProvider`/`WarrantyProvider`/`DispatchProvider` protocols, `Fixture*` implementations wrapping today's JSON tools. Behavior identical today; this is what turns "it's a JSON file" into "it's an interface" for the GTM story.

**Scoped out — liability/confirmation gate.** Audit asked for a hard confirmation gate before any dispatch "commit." A real two-turn gate needs ElevenLabs to call a second tool on the driver's spoken "yes," which requires dashboard-side tool schema work outside this codebase and can't be verified end-to-end without live ElevenLabs access. Implemented the part that's honest and testable today (dispatch is explicitly `simulated`, nothing is actually sent), and documented the real gate as a Phase 2/3 backlog item rather than building an unverifiable stub.

**Test suite**: 20 → 93 tests. Added: HOS tier boundary tests at all 5 thresholds, malformed-input suite (reproduces every P1-1/P1-5 crash), a concurrency test that fires two conversations at once and asserts zero cross-talk (the test that would have caught P0-1), an end-to-end `graph.ainvoke` test, session-registry tests, HMAC tests, and a small property-based eval harness (never omit HOS warning below SEVERE, never claim warranty without a matching policy, always end in a confirmation question) — the AgentSpec-style harness the audit asked for, scoped to what the deterministic template path can assert without needing live LLM calls in CI.

---

## HYBRID pass (Sep 2026) — owned STT+LLM, ElevenLabs TTS retained

**Real LangGraph** (`backend/graph.py`). Router + one branch node per `ROUTING_MAP` intent (fault/wellness/warranty/dispatch/shop/nav_confirm), `synthesize` + `synthesize_retry` around LLM synthesis, `MemorySaver` checkpoint keyed by conversation. Closes ADR 0001's revisit clause — the graph finally grew the branches/retries it promised. Diagram: `docs/architecture.mmd` (source) + `docs/architecture.png` via `scripts/render_graph.py`. *Repercussion:* single-intent turns now skip unrelated agents entirely (wellness check no longer runs shop search); `graph.ainvoke` needs a `thread_id` config — a thin wrapper defaults it from `conversation_id` so existing callers/tests are untouched.

**Owned STT** (`backend/stt.py`, `POST /stt`). Faster-Whisper `small.en` on 16 kHz WAV, Silero VAD with energy fallback, per-request `stt_ms` + rolling p50/p95 emitted to the existing `trace_id` audit trail. Missing install 503s with a hint; tests inject a fake transcriber so CI needs no model weights. *Repercussion:* `faster-whisper` stays commented out of `requirements.txt` (ctranslate2 wheel) — install where STT runs, not in minimal CI images.

**Owned LLM** (`backend/llm.py`). `PROVIDER_LLM=local` tries Ollama `qwen2.5:3b` with Anthropic fallback; `anthropic` default preserves behavior. Template-first (ADR 0004) unchanged — the LLM only ever saw OOD states and still does. *Repercussion:* Ollama OOD phrasing quality unproven vs Sonnet; fallback + degraded template bound the risk.

**Multi-turn nav** (`confirm_nav_yes_no`, `backend/agents/nav_confirm.py`, frontend hold-open). The fault reply's closing yes/no is now a real second tool call through the `nav_confirm` branch (no agents re-run, cache bypassed, `nav_confirmed` emitted); `HomeClient` holds the session open while a "set nav …?" reply awaits its answer. This supersedes the UPGRADE_LOG's earlier "scoped out — confirmation gate" entry: the backend half of the two-turn gate now exists and is testable; remaining dashboard-side step is adding the tool schema in ElevenLabs (documented in CONTRIBUTING).

**Latency eval** (`scripts/eval_latency.py`). 20 scripted utterances, webhook-to-reply p50/p95 + template-hit + HOS-tier table, published to README. Measured 2026-09-06 (CPU, in-process, after warmup): p50 ~156 ms / p95 ~160–190 ms, template 20/20, HOS 20/20.

**Test suite**: 95 → 111. Added `test_graph_branches.py` (branch-per-intent routing, nav yes/no turns, retry-node degradation, thread isolation, webhook-level nav test) and `test_stt_endpoint.py` (transcript + audit trail, 16 kHz enforcement, metrics accumulation, 503 without model).

