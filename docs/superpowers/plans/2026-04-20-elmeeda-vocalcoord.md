# Elmeeda VocalCoord Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a split-screen POC demo — left side is a voice-first truck driver co-pilot powered by ElevenLabs, right side is a live multi-agent pipeline dashboard showing LangGraph agents executing in real-time.

**Architecture:** ElevenLabs SDK runs client-side in the browser; when it fires a tool call, it POSTs to a FastAPI webhook which runs a LangGraph state machine. Agents fan out in parallel via `asyncio.gather`, emitting SSE events that stream to the Next.js dashboard via `EventSource`.

**Tech Stack:** Python 3.11, FastAPI, LangGraph, Anthropic SDK (claude-sonnet-4-6), sse-starlette, Next.js 14, TypeScript, Tailwind CSS, `@elevenlabs/react`, pytest, pytest-asyncio

---

## File Map

```
elmeeda-vocalcoord/
├── backend/
│   ├── main.py                      # FastAPI app, CORS, SSE + webhook endpoints
│   ├── graph.py                     # LangGraph state machine (orchestrator → response)
│   ├── models.py                    # Pydantic models for webhook payload/response
│   ├── events.py                    # asyncio.Queue SSE manager (keyed by conversation_id)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── orchestrator.py          # classify intent + asyncio.gather parallel fan-out
│   │   ├── response.py              # Claude call to synthesize voice reply
│   │   ├── shop_caller.py           # shop search + booking logic + SSE events
│   │   ├── warranty_scout.py        # warranty lookup + claim estimation + SSE events
│   │   ├── wellness_copilot.py      # HOS-aware check-in + SSE events
│   │   └── dispatch_relay.py        # simulated dispatch webhook + SSE events
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── j1939.py                 # fault code parsing + lookup from JSON
│   │   ├── shop_db.py               # shop search/filter/rank from JSON
│   │   └── warranty_db.py           # warranty coverage lookup from JSON
│   ├── data/
│   │   ├── fault_codes.json
│   │   ├── shops.json
│   │   └── warranty_parts.json
│   ├── tests/
│   │   ├── test_j1939.py
│   │   ├── test_shop_db.py
│   │   ├── test_warranty_db.py
│   │   ├── test_orchestrator.py
│   │   └── test_webhook.py
│   └── requirements.txt
│
└── frontend/
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx                 # split-screen root, manages conversationId state
    │   └── globals.css
    ├── components/
    │   ├── DriverView/
    │   │   ├── index.tsx            # left panel container (idle/listening/speaking states)
    │   │   ├── AudioVisualizer.tsx  # Web Audio API frequency bars
    │   │   └── FaultBanner.tsx      # slides in on fault_detected event
    │   └── MissionControl/
    │       ├── index.tsx            # right panel container
    │       ├── AgentCard.tsx        # standby/active/complete tile
    │       ├── AgentPipeline.tsx    # 2×2 grid of AgentCards
    │       └── EventLog.tsx         # scrolling timestamped action feed
    ├── hooks/
    │   ├── useConversation.ts       # ElevenLabs SDK wrapper, exposes start/stop/status
    │   └── useAgentEvents.ts        # SSE EventSource → useReducer dashboard state
    ├── types/
    │   └── events.ts                # AgentEvent union type + AgentState shape
    ├── lib/
    │   └── utils.ts                 # cn() className helper
    ├── .env.local                   # NEXT_PUBLIC_ELEVENLABS_AGENT_ID
    ├── package.json
    ├── tailwind.config.ts
    └── next.config.ts
```

---

## Task 1: Backend project setup

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env`

- [ ] **Step 1: Create backend directory and requirements.txt**

```
backend/requirements.txt:

fastapi==0.115.0
uvicorn[standard]==0.30.6
sse-starlette==2.1.3
langgraph==0.2.55
langchain-core==0.3.20
anthropic==0.40.0
pydantic==2.9.0
pydantic-settings==2.6.0
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.0
python-dotenv==1.0.1
```

- [ ] **Step 2: Create .env file**

```
backend/.env:

ANTHROPIC_API_KEY=your_key_here
ELEVENLABS_AGENT_ID=your_agent_id_here
CORS_ORIGINS=http://localhost:3000
```

- [ ] **Step 3: Install dependencies**

```bash
cd backend
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt backend/.env
git commit -m "chore: backend project setup"
```

---

## Task 2: Mock data files

**Files:**
- Create: `backend/data/fault_codes.json`
- Create: `backend/data/shops.json`
- Create: `backend/data/warranty_parts.json`

- [ ] **Step 1: Create fault_codes.json**

```json
[
  {
    "spn": 4334,
    "fmi": 18,
    "description": "DEF System Pressure Low",
    "severity": "red_stop",
    "plain_english": "Your DEF pump is failing. Engine will derate in ~50 miles if unaddressed.",
    "likely_part": "DEF Pump Assembly",
    "warranty_code": "EPA_EMISSION_COVERAGE"
  },
  {
    "spn": 3251,
    "fmi": 16,
    "description": "DPF Differential Pressure High",
    "severity": "yellow_caution",
    "plain_english": "Your diesel particulate filter needs a regen. Find a safe spot to idle for 20 minutes.",
    "likely_part": null,
    "warranty_code": null
  },
  {
    "spn": 100,
    "fmi": 1,
    "description": "Engine Oil Pressure Low",
    "severity": "red_stop",
    "plain_english": "Critical: pull over safely and shut down immediately. Engine damage risk.",
    "likely_part": "Oil Pressure Sensor",
    "warranty_code": "POWERTRAIN_BASIC"
  },
  {
    "spn": 520192,
    "fmi": 31,
    "description": "SCR Efficiency Below Threshold",
    "severity": "yellow_caution",
    "plain_english": "Emissions system underperforming. Needs shop attention within 500 miles.",
    "likely_part": "SCR Catalyst",
    "warranty_code": "EPA_EMISSION_COVERAGE"
  },
  {
    "spn": 0,
    "fmi": 0,
    "description": "No Active Faults",
    "severity": "advisory",
    "plain_english": "All systems nominal.",
    "likely_part": null,
    "warranty_code": null
  }
]
```

- [ ] **Step 2: Create shops.json**

```json
[
  {
    "id": "shop_001",
    "name": "Freightliner of Columbus",
    "distance_miles": 12,
    "open_bay_time": "2:00 PM",
    "certifications": ["Freightliner", "Detroit"],
    "has_def_pump": true,
    "labor_rate": 145,
    "phone": "614-555-0182"
  },
  {
    "id": "shop_002",
    "name": "Peterbilt Columbus",
    "distance_miles": 18,
    "open_bay_time": "4:30 PM",
    "certifications": ["Peterbilt", "PACCAR"],
    "has_def_pump": true,
    "labor_rate": 155,
    "phone": "614-555-0291"
  },
  {
    "id": "shop_003",
    "name": "Speedco Truck Care I-70",
    "distance_miles": 8,
    "open_bay_time": "Now",
    "certifications": ["General"],
    "has_def_pump": false,
    "labor_rate": 110,
    "phone": "614-555-0344"
  },
  {
    "id": "shop_004",
    "name": "Love's Truck Care #441",
    "distance_miles": 5,
    "open_bay_time": "Now",
    "certifications": ["General"],
    "has_def_pump": false,
    "labor_rate": 95,
    "phone": "614-555-0419"
  }
]
```

- [ ] **Step 3: Create warranty_parts.json**

```json
[
  {
    "warranty_code": "EPA_EMISSION_COVERAGE",
    "part": "DEF Pump Assembly",
    "coverage": "Federal EPA Emissions Warranty — 5yr/100k miles",
    "claim_value": 340,
    "labor_included": true,
    "expires_miles": 87500
  },
  {
    "warranty_code": "POWERTRAIN_BASIC",
    "part": "Oil Pressure Sensor",
    "coverage": "OEM Powertrain Basic — 3yr/36k miles",
    "claim_value": 95,
    "labor_included": false,
    "expires_miles": 31200
  }
]
```

- [ ] **Step 4: Commit**

```bash
git add backend/data/
git commit -m "chore: add mock data files"
```

---

## Task 3: Pydantic models

**Files:**
- Create: `backend/models.py`

- [ ] **Step 1: Write models.py**

```python
# backend/models.py
from pydantic import BaseModel
from typing import Optional


class DriverLocation(BaseModel):
    lat: float
    lon: float
    city: str


class ToolCallPayload(BaseModel):
    type: str = "tool_call"
    conversation_id: str
    tool_name: str
    parameters: dict


class ToolCallResponse(BaseModel):
    result: str
```

- [ ] **Step 2: Verify import works**

```bash
cd backend
python -c "from models import ToolCallPayload, ToolCallResponse; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/models.py
git commit -m "chore: add pydantic models"
```

---

## Task 4: SSE event queue manager

**Files:**
- Create: `backend/events.py`

- [ ] **Step 1: Write events.py**

```python
# backend/events.py
import asyncio
from typing import Dict

_queues: Dict[str, asyncio.Queue] = {}


def get_queue(conversation_id: str) -> asyncio.Queue:
    if conversation_id not in _queues:
        _queues[conversation_id] = asyncio.Queue()
    return _queues[conversation_id]


async def emit(conversation_id: str, event: dict) -> None:
    queue = get_queue(conversation_id)
    await queue.put(event)


def cleanup(conversation_id: str) -> None:
    _queues.pop(conversation_id, None)
```

- [ ] **Step 2: Write test**

```python
# backend/tests/test_events.py
import asyncio
import pytest
from backend.events import get_queue, emit, cleanup


@pytest.mark.asyncio
async def test_emit_puts_event_on_queue():
    conv_id = "test_conv_001"
    cleanup(conv_id)

    await emit(conv_id, {"type": "ping", "data": {}})

    queue = get_queue(conv_id)
    event = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event == {"type": "ping", "data": {}}
    cleanup(conv_id)


@pytest.mark.asyncio
async def test_same_conversation_id_gets_same_queue():
    conv_id = "test_conv_002"
    cleanup(conv_id)

    q1 = get_queue(conv_id)
    q2 = get_queue(conv_id)
    assert q1 is q2
    cleanup(conv_id)
```

- [ ] **Step 3: Run tests**

```bash
cd backend
pytest tests/test_events.py -v
```

Expected: 2 passed

- [ ] **Step 4: Commit**

```bash
git add backend/events.py backend/tests/test_events.py
git commit -m "feat: add SSE event queue manager"
```

---

## Task 5: J1939 fault lookup tool

**Files:**
- Create: `backend/tools/__init__.py`
- Create: `backend/tools/j1939.py`
- Create: `backend/tests/test_j1939.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_j1939.py
import pytest
from backend.tools.j1939 import parse_fault_code, lookup_fault


def test_parse_standard_fault_code():
    spn, fmi = parse_fault_code("SPN 4334 FMI 18")
    assert spn == 4334
    assert fmi == 18


def test_parse_fault_code_case_insensitive():
    spn, fmi = parse_fault_code("spn 100 fmi 1")
    assert spn == 100
    assert fmi == 1


def test_lookup_known_fault_returns_data():
    fault = lookup_fault(4334)
    assert fault is not None
    assert fault["severity"] == "red_stop"
    assert fault["warranty_code"] == "EPA_EMISSION_COVERAGE"


def test_lookup_unknown_fault_returns_none():
    fault = lookup_fault(99999)
    assert fault is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
pytest tests/test_j1939.py -v
```

Expected: ModuleNotFoundError or ImportError

- [ ] **Step 3: Write implementation**

```python
# backend/tools/__init__.py
# (empty)
```

```python
# backend/tools/j1939.py
import json
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).parent.parent / "data" / "fault_codes.json"
_fault_data: list[dict] = []
_by_spn: dict[int, dict] = {}


def _load() -> None:
    global _fault_data, _by_spn
    if _fault_data:
        return
    _fault_data = json.loads(_DATA_PATH.read_text())
    _by_spn = {f["spn"]: f for f in _fault_data}


def parse_fault_code(code: str) -> tuple[int, int]:
    """Parse 'SPN 4334 FMI 18' -> (4334, 18)"""
    parts = code.upper().split()
    spn = int(parts[parts.index("SPN") + 1])
    fmi = int(parts[parts.index("FMI") + 1]) if "FMI" in parts else 0
    return spn, fmi


def lookup_fault(spn: int) -> Optional[dict]:
    _load()
    return _by_spn.get(spn)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_j1939.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/tools/ backend/tests/test_j1939.py
git commit -m "feat: add J1939 fault lookup tool"
```

---

## Task 6: Shop database tool

**Files:**
- Create: `backend/tools/shop_db.py`
- Create: `backend/tests/test_shop_db.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_shop_db.py
from backend.tools.shop_db import search_shops, get_best_shop


def test_search_shops_returns_all_within_radius():
    results = search_shops(max_distance=50)
    assert len(results) == 4


def test_search_shops_filters_by_distance():
    results = search_shops(max_distance=10)
    assert all(s["distance_miles"] <= 10 for s in results)


def test_search_shops_filters_by_part_availability():
    results = search_shops(needs_def_pump=True)
    assert all(s["has_def_pump"] for s in results)
    assert len(results) == 2


def test_get_best_shop_prefers_shop_with_part():
    shops = search_shops(max_distance=50)
    best = get_best_shop(shops, needs_def_pump=True)
    assert best["has_def_pump"] is True


def test_get_best_shop_returns_none_for_empty_list():
    assert get_best_shop([], needs_def_pump=False) is None
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_shop_db.py -v
```

Expected: ImportError

- [ ] **Step 3: Write implementation**

```python
# backend/tools/shop_db.py
import json
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).parent.parent / "data" / "shops.json"
_shops: list[dict] = []


def _load() -> None:
    global _shops
    if _shops:
        return
    _shops = json.loads(_DATA_PATH.read_text())


def search_shops(needs_def_pump: bool = False, max_distance: float = 50) -> list[dict]:
    _load()
    results = [s for s in _shops if s["distance_miles"] <= max_distance]
    if needs_def_pump:
        results = [s for s in results if s.get("has_def_pump")]
    return sorted(results, key=lambda x: x["distance_miles"])


def get_best_shop(shops: list[dict], needs_def_pump: bool = False) -> Optional[dict]:
    if not shops:
        return None
    if needs_def_pump:
        with_part = [s for s in shops if s.get("has_def_pump")]
        if with_part:
            return sorted(with_part, key=lambda x: x["distance_miles"])[0]
    return shops[0]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_shop_db.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/tools/shop_db.py backend/tests/test_shop_db.py
git commit -m "feat: add shop database tool"
```

---

## Task 7: Warranty database tool

**Files:**
- Create: `backend/tools/warranty_db.py`
- Create: `backend/tests/test_warranty_db.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_warranty_db.py
from backend.tools.warranty_db import lookup_warranty


def test_lookup_known_warranty_code():
    result = lookup_warranty("EPA_EMISSION_COVERAGE")
    assert result is not None
    assert result["claim_value"] == 340
    assert result["labor_included"] is True


def test_lookup_powertrain_warranty():
    result = lookup_warranty("POWERTRAIN_BASIC")
    assert result is not None
    assert result["claim_value"] == 95


def test_lookup_unknown_code_returns_none():
    result = lookup_warranty("NONEXISTENT_CODE")
    assert result is None
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_warranty_db.py -v
```

Expected: ImportError

- [ ] **Step 3: Write implementation**

```python
# backend/tools/warranty_db.py
import json
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).parent.parent / "data" / "warranty_parts.json"
_warranties: list[dict] = []
_by_code: dict[str, dict] = {}


def _load() -> None:
    global _warranties, _by_code
    if _warranties:
        return
    _warranties = json.loads(_DATA_PATH.read_text())
    _by_code = {w["warranty_code"]: w for w in _warranties}


def lookup_warranty(warranty_code: str) -> Optional[dict]:
    _load()
    return _by_code.get(warranty_code)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_warranty_db.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/tools/warranty_db.py backend/tests/test_warranty_db.py
git commit -m "feat: add warranty database tool"
```

---

## Task 8: Agent implementations

**Files:**
- Create: `backend/agents/__init__.py`
- Create: `backend/agents/shop_caller.py`
- Create: `backend/agents/warranty_scout.py`
- Create: `backend/agents/wellness_copilot.py`
- Create: `backend/agents/dispatch_relay.py`

- [ ] **Step 1: Create agents/__init__.py**

```python
# backend/agents/__init__.py
# (empty)
```

- [ ] **Step 2: Write shop_caller.py**

```python
# backend/agents/shop_caller.py
from backend.tools.j1939 import parse_fault_code, lookup_fault
from backend.tools.shop_db import search_shops, get_best_shop
from backend.events import emit


async def run_shop_caller(state: dict) -> dict:
    conv_id = state["conversation_id"]

    await emit(conv_id, {
        "type": "agent_start",
        "data": {"agent": "shop_caller", "message": f"Searching certified shops near {state['driver_location']['city']}..."}
    })

    spn, _ = parse_fault_code(state["fault_code"])
    fault = lookup_fault(spn)
    needs_def_pump = fault is not None and fault.get("likely_part") == "DEF Pump Assembly"

    await emit(conv_id, {
        "type": "agent_tool_call",
        "data": {"agent": "shop_caller", "tool": "search_shops", "args": {"radius_miles": 25, "needs_def_pump": needs_def_pump}}
    })

    shops = search_shops(needs_def_pump=needs_def_pump, max_distance=25)
    best = get_best_shop(shops, needs_def_pump=needs_def_pump)

    if best:
        await emit(conv_id, {
            "type": "agent_result",
            "data": {
                "agent": "shop_caller",
                "summary": f"{best['name']} — {best['open_bay_time']}, {best['distance_miles']}mi",
                "value": f"${best['labor_rate']}/hr"
            }
        })
    await emit(conv_id, {"type": "agent_complete", "data": {"agent": "shop_caller"}})

    return {"shop_results": shops, "best_shop": best}
```

- [ ] **Step 3: Write warranty_scout.py**

```python
# backend/agents/warranty_scout.py
from backend.tools.j1939 import parse_fault_code, lookup_fault
from backend.tools.warranty_db import lookup_warranty
from backend.events import emit


async def run_warranty_scout(state: dict) -> dict:
    conv_id = state["conversation_id"]

    await emit(conv_id, {
        "type": "agent_start",
        "data": {"agent": "warranty_scout", "message": "Checking warranty coverage for detected fault..."}
    })

    spn, _ = parse_fault_code(state["fault_code"])
    fault = lookup_fault(spn)

    findings = None
    if fault and fault.get("warranty_code"):
        await emit(conv_id, {
            "type": "agent_tool_call",
            "data": {"agent": "warranty_scout", "tool": "lookup_warranty", "args": {"code": fault["warranty_code"]}}
        })
        findings = lookup_warranty(fault["warranty_code"])

    if findings:
        await emit(conv_id, {
            "type": "agent_result",
            "data": {
                "agent": "warranty_scout",
                "summary": f"{findings['part']} covered — {findings['coverage']}",
                "value": f"${findings['claim_value']} claim"
            }
        })
    else:
        await emit(conv_id, {
            "type": "agent_result",
            "data": {"agent": "warranty_scout", "summary": "No warranty coverage found for this fault"}
        })

    await emit(conv_id, {"type": "agent_complete", "data": {"agent": "warranty_scout"}})

    return {"warranty_findings": findings}
```

- [ ] **Step 4: Write wellness_copilot.py**

```python
# backend/agents/wellness_copilot.py
from backend.events import emit


async def run_wellness_copilot(state: dict) -> dict:
    conv_id = state["conversation_id"]
    hos = state.get("hos_hours_remaining", 8.0)

    await emit(conv_id, {
        "type": "agent_start",
        "data": {"agent": "wellness_copilot", "message": f"Checking driver status — {hos:.1f}hrs HOS remaining..."}
    })

    await emit(conv_id, {
        "type": "agent_tool_call",
        "data": {"agent": "wellness_copilot", "tool": "check_hos_rules", "args": {"hours_remaining": hos}}
    })

    if hos < 2.0:
        message = f"You're down to {hos:.1f} hours on your HOS. After this stop, you'll need a 10-hour reset."
    elif hos < 4.0:
        message = f"You have {hos:.1f} hours left on your clock. The shop stop will eat about 2 hours — plan accordingly."
    else:
        message = f"You have {hos:.1f} hours remaining. Plenty of time to handle this repair and continue your run."

    await emit(conv_id, {
        "type": "agent_result",
        "data": {"agent": "wellness_copilot", "summary": message}
    })
    await emit(conv_id, {"type": "agent_complete", "data": {"agent": "wellness_copilot"}})

    return {"wellness_response": message}
```

- [ ] **Step 5: Write dispatch_relay.py**

```python
# backend/agents/dispatch_relay.py
from backend.events import emit


async def run_dispatch_relay(state: dict) -> dict:
    conv_id = state["conversation_id"]
    load = state.get("load_number", "LOAD-0000")

    await emit(conv_id, {
        "type": "agent_start",
        "data": {"agent": "dispatch_relay", "message": f"Preparing delay notification for {load}..."}
    })

    await emit(conv_id, {
        "type": "agent_tool_call",
        "data": {"agent": "dispatch_relay", "tool": "post_dispatch_webhook", "args": {"load_number": load, "delay_hours": 4}}
    })

    payload = {
        "load_number": load,
        "status": "DELAYED",
        "delay_estimate_hours": 4,
        "reason": "Unscheduled mechanical repair",
        "notified": True
    }

    await emit(conv_id, {
        "type": "agent_result",
        "data": {"agent": "dispatch_relay", "summary": f"{load} — dispatch notified, +4hr delay"}
    })
    await emit(conv_id, {"type": "agent_complete", "data": {"agent": "dispatch_relay"}})
    await emit(conv_id, {
        "type": "dispatch_sent",
        "data": {"load_number": load, "eta_delay": "4 hours"}
    })

    return {"dispatch_payload": payload}
```

- [ ] **Step 6: Commit**

```bash
git add backend/agents/
git commit -m "feat: add shop_caller, warranty_scout, wellness_copilot, dispatch_relay agents"
```

---

## Task 9: Orchestrator + response builder

**Files:**
- Create: `backend/agents/orchestrator.py`
- Create: `backend/agents/response.py`
- Create: `backend/tests/test_orchestrator.py`

- [ ] **Step 1: Write failing orchestrator tests**

```python
# backend/tests/test_orchestrator.py
from backend.agents.orchestrator import classify_intent, ROUTING_MAP


def test_fault_detected_routes_to_three_agents():
    intent = classify_intent("trigger_fault_response", {})
    assert intent == "fault_detected"
    assert set(ROUTING_MAP[intent]) == {"shop_caller", "warranty_scout", "dispatch_relay"}


def test_wellness_check_routes_to_wellness():
    intent = classify_intent("request_wellness_check", {})
    assert intent == "wellness_check"
    assert ROUTING_MAP[intent] == ["wellness_copilot"]


def test_warranty_query_routes_to_warranty():
    intent = classify_intent("query_warranty", {})
    assert intent == "warranty_query"
    assert ROUTING_MAP[intent] == ["warranty_scout"]


def test_unknown_tool_defaults_to_fault_detected():
    intent = classify_intent("unknown_tool", {})
    assert intent == "fault_detected"
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_orchestrator.py -v
```

Expected: ImportError

- [ ] **Step 3: Write orchestrator.py**

```python
# backend/agents/orchestrator.py
import asyncio
from backend.agents.shop_caller import run_shop_caller
from backend.agents.warranty_scout import run_warranty_scout
from backend.agents.wellness_copilot import run_wellness_copilot
from backend.agents.dispatch_relay import run_dispatch_relay
from backend.events import emit

ROUTING_MAP: dict[str, list[str]] = {
    "fault_detected":  ["shop_caller", "warranty_scout", "dispatch_relay"],
    "wellness_check":  ["wellness_copilot"],
    "warranty_query":  ["warranty_scout"],
    "dispatch_update": ["dispatch_relay"],
    "shop_search":     ["shop_caller"],
}

_AGENT_RUNNERS = {
    "shop_caller":      run_shop_caller,
    "warranty_scout":   run_warranty_scout,
    "wellness_copilot": run_wellness_copilot,
    "dispatch_relay":   run_dispatch_relay,
}


def classify_intent(tool_name: str, parameters: dict) -> str:
    mapping = {
        "trigger_fault_response": "fault_detected",
        "request_wellness_check": "wellness_check",
        "query_warranty":         "warranty_query",
        "update_dispatch":        "dispatch_update",
        "shop_search":            "shop_search",
    }
    return mapping.get(tool_name, "fault_detected")


async def orchestrate(state: dict) -> dict:
    conv_id = state["conversation_id"]
    intent = classify_intent(state["tool_name"], state.get("parameters", {}))
    agents = ROUTING_MAP[intent]

    state["intent"] = intent
    state["active_agents"] = agents

    await emit(conv_id, {
        "type": "orchestrator",
        "data": {"intent": intent, "routing_to": agents}
    })

    tasks = [_AGENT_RUNNERS[agent](state) for agent in agents]
    results = await asyncio.gather(*tasks)

    for result in results:
        state.update(result)

    return state
```

- [ ] **Step 4: Write response.py**

```python
# backend/agents/response.py
import anthropic

_client = anthropic.Anthropic()


async def build_voice_reply(state: dict) -> str:
    fault_desc = "Vehicle fault detected"
    if state.get("fault_code"):
        from backend.tools.j1939 import parse_fault_code, lookup_fault
        spn, _ = parse_fault_code(state["fault_code"])
        fault = lookup_fault(spn)
        if fault:
            fault_desc = fault["plain_english"]

    context_parts = []

    if state.get("best_shop"):
        shop = state["best_shop"]
        context_parts.append(
            f"Shop booked: {shop['name']}, {shop['distance_miles']} miles ahead, "
            f"open bay at {shop['open_bay_time']}, has required part: {shop.get('has_def_pump', False)}"
        )

    if state.get("warranty_findings"):
        w = state["warranty_findings"]
        context_parts.append(
            f"Warranty: {w['coverage']}, claim value ${w['claim_value']}, "
            f"labor included: {w['labor_included']}"
        )

    if state.get("dispatch_payload"):
        d = state["dispatch_payload"]
        context_parts.append(f"Dispatch notified: {d['load_number']} delayed ~{d['delay_estimate_hours']} hours")

    if state.get("wellness_response"):
        context_parts.append(f"HOS status: {state['wellness_response']}")

    prompt = f"""You are the Elmeeda Co-Pilot voice assistant for a professional truck driver.

Fault: {fault_desc}

Agent findings:
{chr(10).join(f'- {c}' for c in context_parts)}

Write a single voice reply (2-3 sentences max) that:
1. States the fault and urgency clearly
2. Summarizes what was arranged (shop, warranty, dispatch)
3. Ends with a yes/no confirmation question for the driver

Rules: Be direct. No filler. Driver is behind the wheel. Never say "I" or "I've been"."""

    response = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text
```

- [ ] **Step 5: Run orchestrator tests**

```bash
pytest tests/test_orchestrator.py -v
```

Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add backend/agents/orchestrator.py backend/agents/response.py backend/tests/test_orchestrator.py
git commit -m "feat: add orchestrator and response builder"
```

---

## Task 10: LangGraph state machine

**Files:**
- Create: `backend/graph.py`

- [ ] **Step 1: Write graph.py**

```python
# backend/graph.py
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END


class VocalCoordState(TypedDict):
    conversation_id: str
    tool_name: str
    fault_code: str
    fault_severity: str
    driver_location: dict
    hos_hours_remaining: float
    load_number: str
    intent: str
    active_agents: list[str]
    shop_results: list[dict]
    best_shop: Optional[dict]
    warranty_findings: Optional[dict]
    wellness_response: str
    dispatch_payload: Optional[dict]
    voice_reply: str


async def orchestrator_node(state: VocalCoordState) -> VocalCoordState:
    from backend.agents.orchestrator import orchestrate
    result = await orchestrate(dict(state))
    return VocalCoordState(**result)


async def response_node(state: VocalCoordState) -> VocalCoordState:
    from backend.agents.response import build_voice_reply
    voice_reply = await build_voice_reply(dict(state))
    return {**state, "voice_reply": voice_reply}


def build_graph():
    builder = StateGraph(VocalCoordState)
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("response", response_node)
    builder.set_entry_point("orchestrator")
    builder.add_edge("orchestrator", "response")
    builder.add_edge("response", END)
    return builder.compile()


graph = build_graph()
```

- [ ] **Step 2: Verify graph compiles**

```bash
cd backend
python -c "from graph import graph; print('Graph nodes:', list(graph.get_graph().nodes.keys()))"
```

Expected: `Graph nodes: ['orchestrator', 'response', '__start__', '__end__']` (or similar)

- [ ] **Step 3: Commit**

```bash
git add backend/graph.py
git commit -m "feat: add LangGraph state machine"
```

---

## Task 11: FastAPI app with SSE + webhook endpoints

**Files:**
- Create: `backend/main.py`
- Create: `backend/tests/test_webhook.py`

- [ ] **Step 1: Write main.py**

```python
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

load_dotenv()

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
```

- [ ] **Step 2: Write webhook integration test**

```python
# backend/tests/test_webhook.py
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_tool_call_webhook_returns_voice_reply():
    payload = {
        "type": "tool_call",
        "conversation_id": "test_conv_webhook_001",
        "tool_name": "trigger_fault_response",
        "parameters": {
            "fault_code": "SPN 4334 FMI 18",
            "driver_location": {"lat": 39.96, "lon": -82.99, "city": "Columbus, OH"},
            "hos_hours_remaining": 4.5,
            "load_number": "LOAD-9910"
        }
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/webhook/tool-call", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    assert len(data["result"]) > 10  # non-empty voice reply
```

- [ ] **Step 3: Run tests (requires ANTHROPIC_API_KEY set)**

```bash
cd backend
pytest tests/test_webhook.py -v
```

Expected: 2 passed (test_tool_call_webhook makes a real Claude call — confirm ANTHROPIC_API_KEY is in .env)

- [ ] **Step 4: Start the server to verify manually**

```bash
uvicorn backend.main:app --reload --port 8000
```

Visit `http://localhost:8000/health` — should return `{"status": "ok"}`

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_webhook.py
git commit -m "feat: add FastAPI app with SSE and tool-call webhook"
```

---

## Task 12: Frontend project setup

**Files:**
- Create: `frontend/` (Next.js project)
- Create: `frontend/.env.local`
- Create: `frontend/lib/utils.ts`

- [ ] **Step 1: Scaffold Next.js project**

```bash
cd elmeeda-vocalcoord
npx create-next-app@latest frontend \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --no-src-dir \
  --import-alias "@/*"
```

When prompted, accept defaults.

- [ ] **Step 2: Install additional dependencies**

```bash
cd frontend
npm install @elevenlabs/react framer-motion lucide-react clsx tailwind-merge
```

- [ ] **Step 3: Create .env.local**

```
# frontend/.env.local
NEXT_PUBLIC_ELEVENLABS_AGENT_ID=your_agent_id_here
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

- [ ] **Step 4: Create lib/utils.ts**

```typescript
// frontend/lib/utils.ts
import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

- [ ] **Step 5: Replace globals.css**

```css
/* frontend/app/globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

* {
  box-sizing: border-box;
}

body {
  background-color: #09090b;
  color: #f4f4f5;
  font-family: ui-monospace, 'Cascadia Code', 'Source Code Pro', Menlo, monospace;
}
```

- [ ] **Step 6: Verify dev server starts**

```bash
npm run dev
```

Visit `http://localhost:3000` — should show default Next.js page.

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "chore: frontend Next.js project setup"
```

---

## Task 13: TypeScript event types

**Files:**
- Create: `frontend/types/events.ts`

- [ ] **Step 1: Write events.ts**

```typescript
// frontend/types/events.ts

export type AgentName = 'shop_caller' | 'warranty_scout' | 'wellness_copilot' | 'dispatch_relay'
export type AgentStatus = 'standby' | 'active' | 'complete'
export type FaultSeverity = 'red' | 'yellow' | 'advisory'

export interface AgentCardState {
  status: AgentStatus
  message?: string
  tool?: string
  summary?: string
  value?: string
}

export interface FaultData {
  code: string
  severity: FaultSeverity
  description: string
}

export interface EventLogEntry {
  id: number
  timestamp: number
  agent: string
  message: string
}

export interface AgentState {
  fault: FaultData | null
  faultActive: boolean
  routingTo: AgentName[]
  agents: Record<AgentName, AgentCardState>
  eventLog: EventLogEntry[]
  voiceReply: string | null
}

export const initialAgentState: AgentState = {
  fault: null,
  faultActive: false,
  routingTo: [],
  agents: {
    shop_caller:      { status: 'standby' },
    warranty_scout:   { status: 'standby' },
    wellness_copilot: { status: 'standby' },
    dispatch_relay:   { status: 'standby' },
  },
  eventLog: [],
  voiceReply: null,
}

// SSE event union
export type AgentEvent =
  | { type: 'fault_detected';    data: FaultData }
  | { type: 'orchestrator';      data: { intent: string; routing_to: AgentName[] } }
  | { type: 'agent_start';       data: { agent: AgentName; message: string } }
  | { type: 'agent_tool_call';   data: { agent: AgentName; tool: string; args: Record<string, unknown> } }
  | { type: 'agent_result';      data: { agent: AgentName; summary: string; value?: string } }
  | { type: 'agent_complete';    data: { agent: AgentName } }
  | { type: 'voice_reply_ready'; data: { text: string } }
  | { type: 'dispatch_sent';     data: { load_number: string; eta_delay: string } }
  | { type: 'ping' }
```

- [ ] **Step 2: Commit**

```bash
git add frontend/types/events.ts
git commit -m "chore: add TypeScript event types"
```

---

## Task 14: useAgentEvents and useConversation hooks

**Files:**
- Create: `frontend/hooks/useAgentEvents.ts`
- Create: `frontend/hooks/useConversation.ts`

- [ ] **Step 1: Write useAgentEvents.ts**

```typescript
// frontend/hooks/useAgentEvents.ts
'use client'
import { useEffect, useReducer, useRef } from 'react'
import {
  AgentEvent, AgentState, AgentName, initialAgentState
} from '@/types/events'

let _nextId = 0

type Action = { type: 'EVENT'; payload: AgentEvent } | { type: 'RESET' }

function reducer(state: AgentState, action: Action): AgentState {
  if (action.type === 'RESET') return initialAgentState

  const event = action.payload
  if (event.type === 'ping') return state

  switch (event.type) {
    case 'fault_detected':
      return { ...state, fault: event.data, faultActive: true }

    case 'orchestrator':
      return { ...state, routingTo: event.data.routing_to }

    case 'agent_start':
      return {
        ...state,
        agents: {
          ...state.agents,
          [event.data.agent]: { status: 'active', message: event.data.message }
        }
      }

    case 'agent_tool_call':
      return {
        ...state,
        agents: {
          ...state.agents,
          [event.data.agent]: {
            ...state.agents[event.data.agent as AgentName],
            tool: event.data.tool
          }
        }
      }

    case 'agent_result': {
      const entry = {
        id: _nextId++,
        timestamp: Date.now(),
        agent: event.data.agent,
        message: event.data.summary + (event.data.value ? ` — ${event.data.value}` : '')
      }
      return {
        ...state,
        agents: {
          ...state.agents,
          [event.data.agent]: {
            status: 'complete',
            summary: event.data.summary,
            value: event.data.value
          }
        },
        eventLog: [...state.eventLog, entry]
      }
    }

    case 'voice_reply_ready':
      return { ...state, voiceReply: event.data.text }

    case 'dispatch_sent': {
      const entry = {
        id: _nextId++,
        timestamp: Date.now(),
        agent: 'dispatch_relay',
        message: `${event.data.load_number} notified — +${event.data.eta_delay} delay`
      }
      return { ...state, eventLog: [...state.eventLog, entry] }
    }

    default:
      return state
  }
}

export function useAgentEvents(conversationId: string | null) {
  const [state, dispatch] = useReducer(reducer, initialAgentState)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    dispatch({ type: 'RESET' })
    if (!conversationId) return

    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://localhost:8000'
    const es = new EventSource(`${backendUrl}/events/${conversationId}`)
    esRef.current = es

    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data) as AgentEvent
        dispatch({ type: 'EVENT', payload: event })
      } catch {
        // malformed event, ignore
      }
    }

    return () => {
      es.close()
      esRef.current = null
    }
  }, [conversationId])

  return state
}
```

- [ ] **Step 2: Write useConversation.ts**

```typescript
// frontend/hooks/useConversation.ts
'use client'
import { useConversation as useElevenLabs } from '@elevenlabs/react'
import { useCallback, useState } from 'react'

export type ConversationStatus = 'idle' | 'connecting' | 'connected' | 'error'

export function useConversation(onConversationId: (id: string) => void) {
  const [status, setStatus] = useState<ConversationStatus>('idle')
  const [isSpeaking, setIsSpeaking] = useState(false)

  const conversation = useElevenLabs({
    onConnect: (props) => {
      setStatus('connected')
      if (props.conversationId) {
        onConversationId(props.conversationId)
      }
    },
    onDisconnect: () => {
      setStatus('idle')
      setIsSpeaking(false)
    },
    onError: () => {
      setStatus('error')
    },
    onMessage: (msg) => {
      setIsSpeaking(msg.type === 'agent_response')
    },
  })

  const start = useCallback(async () => {
    setStatus('connecting')
    const agentId = process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID
    if (!agentId) throw new Error('NEXT_PUBLIC_ELEVENLABS_AGENT_ID not set')
    await conversation.startSession({ agentId })
  }, [conversation])

  const stop = useCallback(async () => {
    await conversation.endSession()
    setStatus('idle')
  }, [conversation])

  return { status, isSpeaking, start, stop }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/hooks/
git commit -m "feat: add useAgentEvents and useConversation hooks"
```

---

## Task 15: FaultBanner and AudioVisualizer components

**Files:**
- Create: `frontend/components/DriverView/FaultBanner.tsx`
- Create: `frontend/components/DriverView/AudioVisualizer.tsx`

- [ ] **Step 1: Write FaultBanner.tsx**

```tsx
// frontend/components/DriverView/FaultBanner.tsx
'use client'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, AlertCircle, Info } from 'lucide-react'
import { FaultData } from '@/types/events'
import { cn } from '@/lib/utils'

interface FaultBannerProps {
  fault: FaultData | null
}

const SEVERITY_CONFIG = {
  red:      { bg: 'bg-red-950 border-red-500',    text: 'text-red-400',    icon: AlertTriangle, label: 'RED STOP' },
  yellow:   { bg: 'bg-yellow-950 border-yellow-500', text: 'text-yellow-400', icon: AlertCircle,  label: 'CAUTION' },
  advisory: { bg: 'bg-zinc-900 border-zinc-600',  text: 'text-zinc-400',   icon: Info,           label: 'ADVISORY' },
}

export function FaultBanner({ fault }: FaultBannerProps) {
  const config = fault ? SEVERITY_CONFIG[fault.severity] : null

  return (
    <AnimatePresence>
      {fault && config && (
        <motion.div
          initial={{ y: -80, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -80, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          className={cn(
            'w-full rounded-lg border px-4 py-3 mb-4',
            config.bg
          )}
        >
          <div className="flex items-center gap-3">
            <config.icon className={cn('w-5 h-5 shrink-0', config.text)} />
            <div>
              <div className={cn('text-xs font-bold tracking-widest', config.text)}>
                {config.label}
              </div>
              <div className="text-sm text-zinc-100 font-medium">{fault.description}</div>
              <div className="text-xs text-zinc-400 font-mono">{fault.code}</div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
```

- [ ] **Step 2: Write AudioVisualizer.tsx**

```tsx
// frontend/components/DriverView/AudioVisualizer.tsx
'use client'
import { useEffect, useRef } from 'react'

interface AudioVisualizerProps {
  active: boolean   // true when connected and listening/speaking
  barCount?: number
}

export function AudioVisualizer({ active, barCount = 24 }: AudioVisualizerProps) {
  const barsRef = useRef<HTMLDivElement[]>([])
  const animRef = useRef<number>()
  const analyserRef = useRef<AnalyserNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  useEffect(() => {
    if (!active) {
      cancelAnimationFrame(animRef.current!)
      // reset bars to idle pulse
      barsRef.current.forEach((bar, i) => {
        if (bar) {
          bar.style.height = `${8 + Math.sin(i * 0.4) * 4}px`
          bar.style.opacity = '0.3'
        }
      })
      return
    }

    let audioCtx: AudioContext
    let source: MediaStreamAudioSourceNode

    async function setup() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        streamRef.current = stream
        audioCtx = new AudioContext()
        analyserRef.current = audioCtx.createAnalyser()
        analyserRef.current.fftSize = 64
        source = audioCtx.createMediaStreamSource(stream)
        source.connect(analyserRef.current)

        const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount)

        const draw = () => {
          animRef.current = requestAnimationFrame(draw)
          analyserRef.current!.getByteFrequencyData(dataArray)

          barsRef.current.forEach((bar, i) => {
            if (!bar) return
            const idx = Math.floor((i / barCount) * dataArray.length)
            const value = dataArray[idx] / 255
            const height = 4 + value * 56
            bar.style.height = `${height}px`
            bar.style.opacity = `${0.4 + value * 0.6}`
          })
        }
        draw()
      } catch {
        // mic permission denied — show static animation
        const animate = () => {
          animRef.current = requestAnimationFrame(animate)
          barsRef.current.forEach((bar, i) => {
            if (!bar) return
            const t = Date.now() / 400
            const h = 8 + Math.sin(t + i * 0.5) * 20
            bar.style.height = `${h}px`
            bar.style.opacity = '0.6'
          })
        }
        animate()
      }
    }

    setup()

    return () => {
      cancelAnimationFrame(animRef.current!)
      streamRef.current?.getTracks().forEach(t => t.stop())
      audioCtx?.close()
    }
  }, [active, barCount])

  return (
    <div className="flex items-end justify-center gap-1 h-16">
      {Array.from({ length: barCount }).map((_, i) => (
        <div
          key={i}
          ref={el => { if (el) barsRef.current[i] = el }}
          className="w-1.5 rounded-full bg-amber-400 transition-none"
          style={{ height: '8px', opacity: 0.3 }}
        />
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/DriverView/
git commit -m "feat: add FaultBanner and AudioVisualizer components"
```

---

## Task 16: AgentCard and EventLog components

**Files:**
- Create: `frontend/components/MissionControl/AgentCard.tsx`
- Create: `frontend/components/MissionControl/EventLog.tsx`

- [ ] **Step 1: Write AgentCard.tsx**

```tsx
// frontend/components/MissionControl/AgentCard.tsx
'use client'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { AgentCardState, AgentName } from '@/types/events'

const AGENT_LABELS: Record<AgentName, string> = {
  shop_caller:      'SHOP CALLER',
  warranty_scout:   'WARRANTY SCOUT',
  wellness_copilot: 'WELLNESS CO-PILOT',
  dispatch_relay:   'DISPATCH RELAY',
}

interface AgentCardProps {
  name: AgentName
  state: AgentCardState
}

export function AgentCard({ name, state }: AgentCardProps) {
  const { status, message, tool, summary, value } = state

  return (
    <motion.div
      layout
      className={cn(
        'rounded-lg border p-4 min-h-[100px] transition-colors duration-300',
        status === 'standby' && 'border-zinc-700 opacity-40',
        status === 'active'  && 'border-amber-400 shadow-lg shadow-amber-400/10',
        status === 'complete'&& 'border-emerald-400 shadow-md shadow-emerald-400/10',
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-bold tracking-widest text-zinc-400">
          {AGENT_LABELS[name]}
        </span>
        <div>
          {status === 'active' && (
            <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-ping" />
          )}
          {status === 'complete' && (
            <span className="text-emerald-400 text-sm font-bold">✓</span>
          )}
        </div>
      </div>

      {status === 'active' && (
        <div className="space-y-1">
          {message && <p className="text-xs text-zinc-300">{message}</p>}
          {tool && (
            <p className="text-xs text-zinc-500 font-mono">→ {tool}()</p>
          )}
          <div className="mt-2 h-1 w-full bg-zinc-800 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-amber-400 rounded-full"
              initial={{ width: '0%' }}
              animate={{ width: '85%' }}
              transition={{ duration: 2, ease: 'easeOut' }}
            />
          </div>
        </div>
      )}

      {status === 'complete' && (
        <div className="space-y-1">
          {summary && <p className="text-xs text-zinc-200">{summary}</p>}
          {value && <p className="text-xs text-emerald-400 font-mono">{value}</p>}
        </div>
      )}
    </motion.div>
  )
}
```

- [ ] **Step 2: Write EventLog.tsx**

```tsx
// frontend/components/MissionControl/EventLog.tsx
'use client'
import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { EventLogEntry } from '@/types/events'

interface EventLogProps {
  entries: EventLogEntry[]
}

const AGENT_COLORS: Record<string, string> = {
  shop_caller:      'text-blue-400',
  warranty_scout:   'text-purple-400',
  wellness_copilot: 'text-green-400',
  dispatch_relay:   'text-orange-400',
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function EventLog({ entries }: EventLogProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [entries.length])

  return (
    <div className="bg-zinc-900 rounded-lg border border-zinc-700 p-3 h-48 overflow-y-auto">
      <div className="text-xs font-bold tracking-widest text-zinc-500 mb-2">EVENT LOG</div>
      {entries.length === 0 && (
        <p className="text-xs text-zinc-600 italic">Awaiting activity...</p>
      )}
      <AnimatePresence initial={false}>
        {entries.map((entry) => (
          <motion.div
            key={entry.id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex gap-2 text-xs mb-1"
          >
            <span className="text-zinc-600 shrink-0 font-mono">{formatTime(entry.timestamp)}</span>
            <span className={AGENT_COLORS[entry.agent] ?? 'text-zinc-400'}>✓</span>
            <span className="text-zinc-300">{entry.message}</span>
          </motion.div>
        ))}
      </AnimatePresence>
      <div ref={bottomRef} />
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/MissionControl/AgentCard.tsx frontend/components/MissionControl/EventLog.tsx
git commit -m "feat: add AgentCard and EventLog components"
```

---

## Task 17: AgentPipeline and MissionControl panel

**Files:**
- Create: `frontend/components/MissionControl/AgentPipeline.tsx`
- Create: `frontend/components/MissionControl/index.tsx`

- [ ] **Step 1: Write AgentPipeline.tsx**

```tsx
// frontend/components/MissionControl/AgentPipeline.tsx
'use client'
import { AgentCard } from './AgentCard'
import { AgentState, AgentName } from '@/types/events'

const AGENT_ORDER: AgentName[] = ['shop_caller', 'warranty_scout', 'wellness_copilot', 'dispatch_relay']

interface AgentPipelineProps {
  agents: AgentState['agents']
}

export function AgentPipeline({ agents }: AgentPipelineProps) {
  return (
    <div className="grid grid-cols-2 gap-3">
      {AGENT_ORDER.map((name) => (
        <AgentCard key={name} name={name} state={agents[name]} />
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Write MissionControl/index.tsx**

```tsx
// frontend/components/MissionControl/index.tsx
'use client'
import { AgentPipeline } from './AgentPipeline'
import { EventLog } from './EventLog'
import { AgentState } from '@/types/events'

interface MissionControlProps {
  agentState: AgentState
}

export function MissionControl({ agentState }: MissionControlProps) {
  return (
    <div className="flex flex-col gap-4 h-full">
      <div>
        <div className="text-xs font-bold tracking-widest text-zinc-500 mb-3">
          ELMEEDA BRAIN — MULTI-AGENT PIPELINE
        </div>
        {agentState.routingTo.length > 0 && (
          <div className="text-xs text-amber-400 font-mono mb-3">
            ORCHESTRATOR → [{agentState.routingTo.join(', ')}]
          </div>
        )}
        <AgentPipeline agents={agentState.agents} />
      </div>
      <EventLog entries={agentState.eventLog} />
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/MissionControl/AgentPipeline.tsx frontend/components/MissionControl/index.tsx
git commit -m "feat: add AgentPipeline and MissionControl panel"
```

---

## Task 18: DriverView panel

**Files:**
- Create: `frontend/components/DriverView/index.tsx`

- [ ] **Step 1: Write DriverView/index.tsx**

```tsx
// frontend/components/DriverView/index.tsx
'use client'
import { motion } from 'framer-motion'
import { Mic, MicOff, Radio } from 'lucide-react'
import { AudioVisualizer } from './AudioVisualizer'
import { FaultBanner } from './FaultBanner'
import { ConversationStatus } from '@/hooks/useConversation'
import { FaultData } from '@/types/events'
import { cn } from '@/lib/utils'

interface DriverViewProps {
  status: ConversationStatus
  isSpeaking: boolean
  fault: FaultData | null
  onStart: () => void
  onStop: () => void
}

const STATUS_LABEL: Record<ConversationStatus, string> = {
  idle:       'CO-PILOT STANDING BY',
  connecting: 'CONNECTING...',
  connected:  'CO-PILOT ACTIVE',
  error:      'CONNECTION ERROR',
}

export function DriverView({ status, isSpeaking, fault, onStart, onStop }: DriverViewProps) {
  const isActive = status === 'connected'

  return (
    <div className="flex flex-col h-full">
      <div className="text-xs font-bold tracking-widest text-zinc-500 mb-3">
        THE CAB — DRIVER REALITY
      </div>

      <FaultBanner fault={fault} />

      <div className="flex-1 flex flex-col items-center justify-center gap-6">
        {/* Status indicator */}
        <div className="flex items-center gap-2">
          <motion.div
            className={cn(
              'w-3 h-3 rounded-full',
              status === 'idle'       && 'bg-zinc-600',
              status === 'connecting' && 'bg-yellow-400',
              status === 'connected'  && 'bg-emerald-400',
              status === 'error'      && 'bg-red-500',
            )}
            animate={status === 'connected' ? { scale: [1, 1.2, 1] } : {}}
            transition={{ repeat: Infinity, duration: 2 }}
          />
          <span className="text-xs font-mono tracking-widest text-zinc-400">
            {STATUS_LABEL[status]}
          </span>
        </div>

        {/* Audio visualizer */}
        <AudioVisualizer active={isActive} />

        {/* Speaking indicator */}
        {isActive && (
          <div className="flex items-center gap-2">
            <Radio className={cn('w-4 h-4', isSpeaking ? 'text-amber-400 animate-pulse' : 'text-zinc-600')} />
            <span className="text-xs font-mono text-zinc-500">
              {isSpeaking ? 'CO-PILOT SPEAKING' : 'LISTENING...'}
            </span>
          </div>
        )}

        {/* Start / Stop button */}
        {status === 'idle' || status === 'error' ? (
          <button
            onClick={onStart}
            className="flex items-center gap-2 px-6 py-3 rounded-lg bg-amber-400 text-zinc-950 font-bold text-sm tracking-wider hover:bg-amber-300 transition-colors"
          >
            <Mic className="w-4 h-4" />
            START CO-PILOT
          </button>
        ) : (
          <button
            onClick={onStop}
            disabled={status === 'connecting'}
            className="flex items-center gap-2 px-6 py-3 rounded-lg border border-zinc-600 text-zinc-400 text-sm tracking-wider hover:border-zinc-400 transition-colors disabled:opacity-40"
          >
            <MicOff className="w-4 h-4" />
            END SESSION
          </button>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/DriverView/index.tsx
git commit -m "feat: add DriverView panel"
```

---

## Task 19: Root page — split screen assembly

**Files:**
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Write layout.tsx**

```tsx
// frontend/app/layout.tsx
import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Elmeeda VocalCoord',
  description: 'Voice-first fleet maintenance co-pilot',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-zinc-950 text-zinc-100">{children}</body>
    </html>
  )
}
```

- [ ] **Step 2: Write page.tsx**

```tsx
// frontend/app/page.tsx
'use client'
import { useState } from 'react'
import { DriverView } from '@/components/DriverView'
import { MissionControl } from '@/components/MissionControl'
import { useConversation } from '@/hooks/useConversation'
import { useAgentEvents } from '@/hooks/useAgentEvents'

export default function Home() {
  const [conversationId, setConversationId] = useState<string | null>(null)
  const agentState = useAgentEvents(conversationId)
  const { status, isSpeaking, start, stop } = useConversation(setConversationId)

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-amber-400" />
          <span className="text-sm font-bold tracking-widest text-zinc-200">ELMEEDA VOCALCOORD</span>
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${status === 'connected' ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-600'}`} />
          <span className="text-xs font-mono text-zinc-500">{status.toUpperCase()}</span>
        </div>
      </header>

      {/* Split screen */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Driver Reality */}
        <div className="w-2/5 border-r border-zinc-800 p-6">
          <DriverView
            status={status}
            isSpeaking={isSpeaking}
            fault={agentState.fault}
            onStart={start}
            onStop={stop}
          />
        </div>

        {/* Right: Elmeeda Brain */}
        <div className="w-3/5 p-6 overflow-y-auto">
          <MissionControl agentState={agentState} />
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Start frontend and verify it renders**

```bash
cd frontend
npm run dev
```

Visit `http://localhost:3000` — should show dark split screen with "CO-PILOT STANDING BY" on left, four dimmed agent cards on right.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/
git commit -m "feat: assemble split-screen root page"
```

---

## Task 20: ElevenLabs agent configuration

This task is done in the ElevenLabs dashboard — no code files changed.

- [ ] **Step 1: Create agent in ElevenLabs dashboard**

Go to `elevenlabs.io` → Conversational AI → Create Agent.

- **Name:** Elmeeda Co-Pilot
- **Voice:** Aria (or any professional-sounding voice with Flash v2.5 model)
- **First message:** `I'm your Elmeeda Co-Pilot. I'm connected to your vehicle systems. Say check my truck to run a diagnostic, or I'll alert you automatically if I detect a fault.`
- **System prompt:**
```
You are the Elmeeda Co-Pilot, a voice assistant for professional long-haul truck drivers.
Be calm, direct, and efficient. Never ask the driver to look at a screen.
Always confirm actions before executing them.
When a fault is detected, lead with severity and immediate action required.
When you receive a tool result, read the voice_reply field to the driver exactly as written without modification.
```

- [ ] **Step 2: Add tools to the agent**

Add four tools of type "Webhook". For each tool, set the webhook URL to `https://your-ngrok-url/webhook/tool-call` (use ngrok during local dev — see Step 4).

**Tool 1: trigger_fault_response**
- Description: "Triggered when a vehicle fault is detected or when the driver asks to check their truck"
- Parameters:
  - `fault_code` (string): "The J1939 fault code, e.g. SPN 4334 FMI 18"
  - `driver_location` (object): "Driver's current location with lat, lon, city"
  - `hos_hours_remaining` (number): "Hours of service remaining for the driver"
  - `load_number` (string): "Current load/shipment number"

**Tool 2: request_wellness_check**
- Description: "Triggered when the driver requests a wellness check-in or HOS status"
- Parameters:
  - `hos_hours_remaining` (number)
  - `driver_location` (object)

**Tool 3: query_warranty**
- Description: "Triggered when the driver asks about warranty coverage for a part or repair"
- Parameters:
  - `fault_code` (string)

**Tool 4: update_dispatch**
- Description: "Triggered when the driver wants to notify dispatch of a delay or status update"
- Parameters:
  - `load_number` (string)
  - `delay_hours` (number)

- [ ] **Step 3: Copy agent ID to .env.local**

```
NEXT_PUBLIC_ELEVENLABS_AGENT_ID=agent_xxxxxxxxxxxxxxxx
```

- [ ] **Step 4: Expose backend via ngrok for ElevenLabs webhooks**

```bash
# In a separate terminal
ngrok http 8000
```

Copy the `https://xxxx.ngrok-free.app` URL. Update the webhook URL in each ElevenLabs tool to `https://xxxx.ngrok-free.app/webhook/tool-call`.

- [ ] **Step 5: Commit updated .env.local placeholder**

```bash
git add frontend/.env.local
git commit -m "chore: add ElevenLabs agent ID env var"
```

---

## Task 21: End-to-end smoke test

- [ ] **Step 1: Start all services**

Terminal 1 (backend):
```bash
cd backend
uvicorn backend.main:app --reload --port 8000
```

Terminal 2 (ngrok):
```bash
ngrok http 8000
```
Update ElevenLabs tool webhook URLs to the new ngrok URL.

Terminal 3 (frontend):
```bash
cd frontend
npm run dev
```

- [ ] **Step 2: Run full demo flow**

1. Open `http://localhost:3000`
2. Click "START CO-PILOT" — browser requests mic permission, ElevenLabs connects
3. Say: **"Check my truck"**
4. Verify in browser:
   - Red fault banner slides in on left: "DEF System Pressure Low / SPN 4334 FMI 18"
   - Right side: Orchestrator line appears: `ORCHESTRATOR → [shop_caller, warranty_scout, dispatch_relay]`
   - Three agent cards flip to active (amber) simultaneously
   - Cards go green one by one with summaries
   - Event log fills with timestamped entries
5. ElevenLabs Co-Pilot speaks the voice reply
6. Say: **"Yes, book it"** — conversation continues naturally

- [ ] **Step 3: Run all backend tests one final time**

```bash
cd backend
pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat: elmeeda vocalcoord POC complete — multi-agent voice demo"
```

---

## Self-Review Against Spec

| Spec Requirement | Task Covered |
|---|---|
| ElevenLabs React SDK client-side | Task 14, 15, 18, 19 |
| LangGraph state machine | Task 10 |
| Parallel agent fan-out via asyncio.gather | Task 9 |
| SSE real-time dashboard sync | Task 4, 11 |
| Shop Caller agent | Task 8 |
| Warranty Scout agent | Task 8 |
| Wellness Co-Pilot agent | Task 8 |
| Dispatch Relay agent | Task 8 |
| FaultBanner slides in on fault_detected | Task 15 |
| AgentCard standby/active/complete states | Task 16 |
| EventLog scrolling feed | Task 16 |
| Audio visualizer (Web Audio API) | Task 15 |
| Split-screen layout (40/60 left/right) | Task 19 |
| Dark theme zinc-950 | Task 12, 19 |
| Mock data (shops, faults, warranty) | Task 2 |
| Claude claude-sonnet-4-6 voice reply synthesis | Task 9 |
| ElevenLabs agent config (4 tools) | Task 20 |
| ngrok for local webhook testing | Task 20 |
| All backend tests passing | Tasks 4-7, 9, 11 |
