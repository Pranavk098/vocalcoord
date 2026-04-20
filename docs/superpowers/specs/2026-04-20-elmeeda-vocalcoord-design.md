# Elmeeda VocalCoord — Design Spec
**Date:** 2026-04-20  
**Purpose:** Job application POC for Elmeeda (CTO demo via Loom)  
**Deliverable:** Working prototype + 3-minute Loom walkthrough

---

## 1. Problem Statement

Truck drivers cannot look at screens while driving. Elmeeda's existing decision layer (Shop Caller, Warranty Scout, Update Relay) is web/text-driven — it serves fleet managers, not the driver at the point of impact. This POC bridges that gap with a voice-first Co-Pilot that demonstrates Elmeeda's full multi-agent architecture in a visually compelling split-screen demo.

---

## 2. Goal

Convince Elmeeda's CTO to hire by demonstrating:
- Real multi-agent orchestration (LangGraph, not a single chatbot)
- ElevenLabs Conversational AI SDK integration with tool calling
- Eval/observability thinking (live agent activity dashboard)
- Deliberate product judgment (what was NOT built and why)

---

## 3. Architecture Overview

```
Browser (Next.js)
├── LEFT:  ElevenLabs SDK ──WebSocket──► ElevenLabs Servers
│          (audio stream)                      │
│                                     tool call webhook (POST)
│                                              │
├── RIGHT: Dashboard ◄──SSE──── FastAPI ◄──────┘
           (agent panel)          │
                              LangGraph
                        ┌─────────┴──────────┐
                  ShopAgent  WarrantyAgent  WellnessAgent  DispatchRelay
```

**Key principle:** ElevenLabs handles all audio client-side. Tool calls POST to FastAPI which runs LangGraph and streams SSE events back to the dashboard. The browser holds an open `EventSource` connection keyed by `conversation_id`.

---

## 4. Project Structure

```
elmeeda-vocalcoord/
├── frontend/                        # Next.js 14 (App Router)
│   ├── app/
│   │   └── page.tsx                 # Split-screen demo root
│   ├── components/
│   │   ├── DriverView/
│   │   │   ├── AudioVisualizer.tsx  # Web Audio API amplitude bars
│   │   │   └── FaultBanner.tsx      # Slides in on fault_detected event
│   │   └── MissionControl/
│   │       ├── AgentPipeline.tsx    # 2x2 grid of AgentCards
│   │       ├── AgentCard.tsx        # standby/active/complete states
│   │       └── EventLog.tsx         # Scrolling timestamped action log
│   └── hooks/
│       ├── useConversation.ts       # ElevenLabs SDK wrapper
│       └── useAgentEvents.ts        # SSE subscriber → dashboard state
│
├── backend/                         # FastAPI + LangGraph (Python)
│   ├── main.py                      # FastAPI app + SSE endpoint
│   ├── graph.py                     # LangGraph state machine
│   ├── agents/
│   │   ├── orchestrator.py          # Intent classification + routing
│   │   ├── shop_caller.py
│   │   ├── warranty_scout.py
│   │   ├── wellness_copilot.py
│   │   └── dispatch_relay.py
│   ├── tools/
│   │   ├── shop_db.py
│   │   ├── warranty_db.py
│   │   └── j1939.py
│   └── data/
│       ├── shops.json
│       ├── fault_codes.json
│       └── warranty_parts.json
│
└── docs/superpowers/specs/
    └── 2026-04-20-elmeeda-vocalcoord-design.md
```

---

## 5. Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Frontend | Next.js 14 + Tailwind | Fast, SSE-native, polished demo UI |
| Voice | `@elevenlabs/react` SDK | Client-side WS, `useConversation` hook |
| Backend | FastAPI (Python) | Async, matches job requirement ("strong in Python") |
| Orchestration | LangGraph | State machine agent routing — exactly what Elmeeda uses |
| LLM | Claude claude-sonnet-4-6 (Anthropic SDK) | Tool calling, reasoning layer |
| Real-time sync | SSE (`asyncio.Queue` per session) | No infra, unidirectional, perfect for dashboard |

---

## 6. LangGraph State Machine

### State Schema
```python
class VocalCoordState(TypedDict):
    conversation_id: str
    fault_code: str           # e.g. "SPN 4334 FMI 18"
    fault_severity: str       # "red_stop" | "yellow_caution" | "advisory"
    driver_location: dict     # {lat, lon, city}
    hos_hours_remaining: float
    intent: str               # classified by orchestrator
    active_agents: list[str]
    shop_results: list[dict]
    warranty_findings: dict
    wellness_response: str
    dispatch_payload: dict
    voice_reply: str          # returned to ElevenLabs
    sse_events: list[dict]    # accumulated for dashboard
```

### Routing Map
```python
ROUTING_MAP = {
    "fault_detected":   ["shop_caller", "warranty_scout", "dispatch_relay"],
    "wellness_check":   ["wellness_copilot"],
    "warranty_query":   ["warranty_scout"],
    "dispatch_update":  ["dispatch_relay"],
    "shop_search":      ["shop_caller"],
}
```

For `fault_detected`, all three operational agents run **in parallel** via LangGraph's `Send` API. This is the key demo moment — three cards light up simultaneously.

### Sub-Agent Responsibilities

| Agent | Input | Tools | Output |
|---|---|---|---|
| **Shop Caller** | fault_code, location, severity | `search_shops()`, `check_bay_availability()`, `book_appointment()` | Nearest certified shop + ETA |
| **Warranty Scout** | fault_code, part | `lookup_warranty_coverage()`, `estimate_claim_value()` | Coverage + $ value |
| **Wellness Co-Pilot** | HOS hours, drive streak | `check_hos_rules()`, `generate_checkin()` | Empathetic voice message |
| **Dispatch Relay** | delay estimate, load number | `post_dispatch_webhook()` | Confirmation sent |

---

## 7. ElevenLabs Configuration

```yaml
agent_name: "Elmeeda Co-Pilot"
voice: Flash v2.5          # sub-400ms latency
first_message: >
  "I'm your Elmeeda Co-Pilot. I'm connected to your vehicle systems.
   Say 'check my truck' to run a diagnostic."
system_prompt: |
  You are the Elmeeda Co-Pilot for professional long-haul truck drivers.
  Be calm, direct, and efficient. Never ask the driver to look at a screen.
  Always confirm actions before executing them. Lead with severity and
  immediate action when a fault is detected.
tools:
  - trigger_fault_response
  - request_wellness_check
  - query_warranty
  - update_dispatch
```

### Tool Call Webhook Payload (ElevenLabs → FastAPI)
```json
{
  "type": "tool_call",
  "conversation_id": "conv_abc123",
  "tool_name": "trigger_fault_response",
  "parameters": {
    "fault_code": "SPN 4334 FMI 18",
    "driver_location": { "lat": 39.96, "lon": -82.99, "city": "Columbus, OH" },
    "hos_hours_remaining": 4.5,
    "load_number": "LOAD-9910"
  }
}
```

FastAPI returns the voice reply **synchronously** (ElevenLabs blocks waiting for it). SSE events fire **asynchronously** to the dashboard in parallel.

---

## 8. SSE Event Schema

```typescript
type AgentEvent =
  | { type: "fault_detected";    data: { code: string; severity: "red" | "yellow" | "advisory"; description: string } }
  | { type: "orchestrator";      data: { intent: string; routing_to: string[] } }
  | { type: "agent_start";       data: { agent: AgentName; message: string } }
  | { type: "agent_tool_call";   data: { agent: AgentName; tool: string; args: Record<string, unknown> } }
  | { type: "agent_result";      data: { agent: AgentName; summary: string; value?: string } }
  | { type: "agent_complete";    data: { agent: AgentName } }
  | { type: "voice_reply_ready"; data: { text: string } }
  | { type: "dispatch_sent";     data: { load_number: string; eta_delay: string } }
```

### Example Stream (DEF fault scenario, primary Loom demo path)
```
t=0ms    fault_detected    → SPN 4334, severity: red, "DEF Pressure Low"
t=50ms   orchestrator      → routing_to: [shop_caller, warranty_scout, dispatch_relay]
t=55ms   agent_start×3     → all three agents activate simultaneously
t=120ms  agent_tool_call   → shop_caller: search_shops({ radius_miles: 25 })
t=180ms  agent_result      → warranty_scout: "DEF pump covered — $340 claim"
t=210ms  agent_result      → shop_caller: "Freightliner Columbus — 2PM, 12mi"
t=230ms  agent_result      → dispatch_relay: "LOAD-9910 notified — +4hr delay"
t=240ms  voice_reply_ready → full voice reply text
```

---

## 9. UI Design

### Layout
Full-width dark split screen (`zinc-950` background):
- **Left 40%** — DriverView: fault banner + audio visualizer + transcript line
- **Right 60%** — MissionControl: 2×2 agent grid + event log

### DriverView States
| State | Visual |
|---|---|
| Idle | Pulsing circle, "Co-Pilot Standing By" |
| Listening | Audio bars animated from mic amplitude (Web Audio API) |
| Speaking | Audio bars animated from TTS amplitude, current text below |

Single "Start Co-Pilot" button to init ElevenLabs session. No other controls — entirely voice-driven after that.

### AgentCard States
| State | Border | Content |
|---|---|---|
| Standby | `zinc-700` dimmed | Agent name only |
| Active | `amber-400` pulsing | Message + tool name + progress bar |
| Complete | `emerald-400` solid | Summary + value (e.g. "$340 claim") |

### Color Language
| Signal | Tailwind |
|---|---|
| Red Stop fault | `red-500` flash |
| Agent active | `amber-400` pulse |
| Agent complete | `emerald-400` |
| Background | `zinc-950` |
| Text | `zinc-100` |

Dark theme is intentional — reads as industrial tool, makes state transitions pop in the Loom.

---

## 10. Simulated Data Layer

Three JSON files, structured to mirror real API responses (OEM swap = URL change only):

### `fault_codes.json` — 5 faults covering full severity spectrum
Primary demo fault: **SPN 4334 FMI 18** (DEF Pressure Low, red stop, warranty eligible)

### `shops.json` — 4 shops near Columbus, OH
- Freightliner Columbus: 12mi, 2PM bay, has DEF pump ✓ ← demo winner
- Peterbilt Columbus: 18mi, 4:30PM bay, has DEF pump ✓
- Speedco I-70: 8mi, open now, no DEF pump
- Love's #441: 5mi, open now, no DEF pump

### `warranty_parts.json` — EPA emissions + powertrain coverage
DEF Pump: EPA Emissions Warranty, $340 claim value, labor included

---

## 11. What Was NOT Built (and Why)

| Feature | Reason excluded |
|---|---|
| ELD compliance integration | Geotab/Samsara own this hardware layer. POC integrates with existing ELD data via API, not a competing implementation. |
| Driver-facing camera | Research shows camera monitoring is the #1 reason for driver resistance. Elmeeda's edge is "support-first," not surveillance. |
| In-cabin comfort controls (temp, radio) | OEM domain. Elmeeda's value is in the maintenance and logistics workflow. |
| Real OEM API calls | Mock data is structured identically to Detroit Connect / PACCAR Connect responses. Week 1 of a real engagement = swap the URLs. |

---

## 12. 3-Week Roadmap (Post-POC)

**Week 1:** Live Samsara/Geotab webhook integration — real fault codes trigger the flow  
**Week 2:** ElevenLabs Voice Design persona tuning + acoustic filtering for cab noise  
**Week 3:** Multi-agent dispatch coordination — Co-Pilot negotiates new pickup window with shipper autonomously, presents solution to driver for voice approval

---

## 13. ROI Signals (for Loom narrative)

| Financial Lever | Industry Loss | Elmeeda Intervention | Annual Impact (100 trucks) |
|---|---|---|---|
| Mechanical Downtime | $400-700/hr | 15% reduction via faster shop booking | $315,000 |
| Warranty Leakage | 60-80% of claims missed | 50% recovery via voice capture | $240,000 |
| Driver Turnover | $8,000-12,000/driver | 10% reduction via wellness support | $150,000 |
| **Total** | | | **$705,000** |

---

## 14. Loom Script (3 minutes)

**Minute 1 (0:00–1:00) — The Incident**
- Start Co-Pilot → fault triggered via "check my truck"
- FaultBanner: RED STOP DEF Pressure SPN 4334
- Three agent cards light up simultaneously (amber pulse)
- Cards go green: shop booked, warranty filed, dispatch notified
- Co-Pilot speaks full resolution in one coherent sentence
- Driver says "Yes, book it" — confirmation fires

**Minute 2 (1:00–2:00) — The Decision Layer**
- Walk the dashboard: parallel routing, not sequential
- Highlight warranty recovery: $340 that would have been lost
- Highlight dispatch relay: automated, not a driver phone call 45min later
- Point to event log: "This is the beginning of an eval layer"

**Minute 3 (2:00–3:00) — What I Didn't Build & Roadmap**
- Three deliberate exclusions with product reasoning
- 3-week roadmap to production-ready integration
- Close: "The driver never touched a screen."
