# Elmeeda VocalCoord

> AI voice co-pilot for long-haul truck drivers — hands-free fault response, shop booking, warranty lookup, HOS compliance, and dispatch notification in under 10 seconds.

---

## The Problem

A truck driver on a 500-mile run hits a DEF system fault. To handle it properly they need to:

1. Decode the J1939 fault code
2. Find a certified shop nearby with the part in stock
3. Check if the repair is under warranty
4. Verify they have enough hours-of-service left
5. Notify dispatch of the delay

That's four separate tasks — none of which can be done safely while driving. **VocalCoord does all of it in a single voice exchange.**

---

## Demo

```
Driver:  "I've got SPN 4334 FMI 18, I'm near Columbus, 3 hours left on my clock, running load FRT-28470."

System:  "Your DEF pump is failing — engine will derate in ~50 miles. Bay booked at Freightliner of
          Columbus, 12 miles ahead at 2 PM. Repair is covered under the EPA Emissions Warranty at no
          cost to you. Dispatch notified on FRT-28470 with a 4-hour delay. Ready to set nav — yes or no?"
```

Four agents. One voice reply. Hands never leave the wheel.

---

## Architecture

```
ElevenLabs Voice (STT + TTS)
        │
        ▼ webhook (tool call)
  FastAPI Backend
        │
        ▼
  LangGraph Orchestrator
        │
   ┌────┴─────────────────────────┐
   │          parallel            │
   ▼          asyncio.gather      ▼
Shop Caller   Warranty Scout   Wellness Co-Pilot   Dispatch Relay
   │               │                │                   │
   └───────────────┴────────────────┴───────────────────┘
                        │
                        ▼
              Claude Sonnet (voice reply)
                        │
                        ▼ SSE stream
              Next.js Dashboard (real-time)
```

**Frontend** streams every agent event via Server-Sent Events — the Mission Control panel shows the full pipeline firing in real time, making the invisible visible for demos and fleet managers.

---

## Stack

| Layer | Technology |
|---|---|
| Voice | ElevenLabs Conversational AI |
| Backend | Python 3.11, FastAPI, uvicorn |
| Agent orchestration | LangGraph |
| LLM (voice synthesis) | Claude Sonnet 4.6 (Anthropic) |
| Real-time events | SSE (sse-starlette) |
| Frontend | Next.js 16, React 19, TypeScript |

---

## Project Structure

```
elmeeda-vocalcoord/
├── backend/
│   ├── main.py                  # FastAPI server, webhook handler, SSE stream
│   ├── graph.py                 # LangGraph state machine
│   ├── events.py                # Per-conversation async event queues
│   ├── models.py                # Pydantic models
│   ├── agents/
│   │   ├── orchestrator.py      # Intent classification + parallel agent routing
│   │   ├── shop_caller.py       # Nearest certified shop with part availability
│   │   ├── warranty_scout.py    # Warranty coverage lookup by fault code
│   │   ├── wellness_copilot.py  # FMCSA HOS compliance check (5 severity tiers)
│   │   ├── dispatch_relay.py    # Delay notification with severity-based ETA
│   │   └── response.py          # Claude voice reply synthesizer
│   ├── tools/
│   │   ├── j1939.py             # SAE J1939 fault code parser (SPN/FMI)
│   │   ├── shop_db.py           # Shop search and ranking
│   │   └── warranty_db.py       # Warranty claims lookup
│   ├── data/
│   │   ├── fault_codes.json     # J1939 SPN lookup table (10 codes)
│   │   ├── shops.json           # Shop database (6 Columbus-area shops)
│   │   └── warranty_parts.json  # Warranty policies (4 coverage types)
│   └── tests/                   # 20 tests — pytest + pytest-asyncio
│
└── frontend/
    ├── app/
    │   ├── page.tsx             # Root (force-dynamic)
    │   ├── layout.tsx           # Global layout
    │   └── HomeClient.tsx       # Split-screen container + auto-end logic
    ├── components/
    │   ├── DriverView/          # Fault banner, audio visualizer, mic button
    │   └── MissionControl/      # Agent pipeline, event log, voice reply panel
    ├── hooks/
    │   ├── useConversation.ts   # ElevenLabs SDK wrapper
    │   └── useAgentEvents.ts    # SSE listener + state reducer
    └── types/
        └── events.ts            # Shared event + agent state types
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- [Anthropic API key](https://console.anthropic.com)
- [ElevenLabs account](https://elevenlabs.io) with a Conversational AI agent configured

### 1. Clone

```bash
git clone https://github.com/Pranavk098/elmeeda-vocalcoord.git
cd elmeeda-vocalcoord
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
ELEVENLABS_AGENT_ID=agent_...
CORS_ORIGINS=http://localhost:3000
```

Start the server:

```bash
uvicorn backend.main:app --reload
```

Backend runs at `http://localhost:8000`. Verify: `http://localhost:8000/health`

### 3. Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_ELEVENLABS_AGENT_ID=agent_...
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

Start the dev server:

```bash
npm run dev
```

Frontend runs at `http://localhost:3000`.

### 4. ElevenLabs Agent Configuration

In your ElevenLabs agent settings, add a **tool** named `trigger_fault_response` with these parameters:

| Parameter | Type | Description |
|---|---|---|
| `fault_code` | string | J1939 fault code e.g. "SPN 4334 FMI 18" |
| `driver_location` | string | City or coordinates |
| `hos_hours_remaining` | number | Hours left on 11-hour driving limit |
| `load_number` | string | Freight load identifier |

Set the webhook URL to: `http://YOUR_BACKEND_URL/webhook/tool-call`

### 5. Run Tests

```bash
cd backend
python -m pytest tests/ -v
```

20 tests, all passing.

---

## How It Works

### Fault Flow

1. Driver speaks → ElevenLabs STT extracts intent + parameters
2. ElevenLabs calls `trigger_fault_response` webhook on the backend
3. Backend emits `fault_detected` SSE event → dashboard lights up
4. LangGraph fires four agents **in parallel** via `asyncio.gather`:
   - **Shop Caller** — filters shops by distance, part availability, certification
   - **Warranty Scout** — maps SPN → warranty code → coverage + claim value
   - **Wellness Co-Pilot** — evaluates HOS against 5 FMCSA rule tiers
   - **Dispatch Relay** — builds delay payload (severity-based: +4hr red, +2hr yellow)
5. Claude synthesizes all findings into a ≤200-token voice reply
6. ElevenLabs TTS speaks the reply; session auto-ends 2.5s after speech finishes

### Re-trigger Protection

ElevenLabs can re-fire the tool if the driver says anything after the reply (yes/no, background noise). The backend caches the completed reply per conversation ID and returns it instantly on repeat calls — no agents re-run, no duplicate SSE events.

### HOS Tiers (FMCSA 49 CFR Part 395)

| Remaining | Status | Action |
|---|---|---|
| < 1.0 hr | CRITICAL | Cannot legally drive after stop — 10-hr reset required |
| 1.0–2.0 hrs | SEVERE | Repair exhausts HOS — coordinate reset location |
| 2.0–3.5 hrs | CAUTION | Tight margin — flags 30-min break rule |
| 3.5–6.0 hrs | WATCH | Enough room — reminds about 8-hr continuous limit |
| ≥ 6.0 hrs | CLEAR | HOS not a constraint |

---

## What Was Intentionally Left Out

- **Real telematics integration** — production version connects to Samsara, Motive, or Geotab APIs for live fault streaming directly from the ECU
- **GPS-aware shop search** — Google Maps Places API + real fleet certification filtering replaces the static JSON database
- **TMS dispatch integration** — real dispatch goes through McLeod, TMW, or Samsara Dispatch webhooks
- **Driver history** — persistent HOS logs, rest history, and load history for richer compliance reasoning
- **Multi-language support** — Spanish is the obvious next language given the driver demographic

---

## License

MIT
