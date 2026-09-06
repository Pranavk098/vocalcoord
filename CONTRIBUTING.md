# Contributing to Elmeeda VocalCoord

Local development setup, running the app, and running tests.

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- [Anthropic API key](https://console.anthropic.com)
- [ElevenLabs account](https://elevenlabs.io) with a Conversational AI agent configured

## 1. Clone

```bash
git clone https://github.com/Pranavk098/elmeeda-vocalcoord.git
cd elmeeda-vocalcoord
```

## 2. Backend

Install dependencies from `backend/`:

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

Create `backend/.env` (see `backend/.env.example` for the full list of variables):

```env
ANTHROPIC_API_KEY=sk-ant-...
ELEVENLABS_AGENT_ID=agent_...
CORS_ORIGINS=http://localhost:3000
```

Start the server **from the repo root** — not from inside `backend/`:

```bash
uvicorn backend.main:app --reload
```

> **Why repo root, not `backend/`:** `backend/main.py` is imported as the
> `backend.main` package, and `backend/tests/` import via `from backend.main
> import app` — both only resolve when the current working directory is the
> repo root. `main.py` also loads `backend/.env` via a relative path
> (`load_dotenv(dotenv_path="backend/.env")`), which likewise assumes the
> process is started from the repo root. Running `cd backend && uvicorn
> main:app --reload` breaks both the import path and the `.env` lookup.

Backend runs at `http://localhost:8000`. Verify: `http://localhost:8000/health`

## 3. Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local` (see `frontend/.env.example`):

```env
NEXT_PUBLIC_ELEVENLABS_AGENT_ID=agent_...
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

Start the dev server:

```bash
npm run dev
```

Frontend runs at `http://localhost:3000`.

## 4. ElevenLabs Agent Configuration

In your ElevenLabs agent settings, add a **tool** named `trigger_fault_response` with these parameters:

| Parameter | Type | Description |
|---|---|---|
| `fault_code` | string | J1939 fault code e.g. "SPN 4334 FMI 18" |
| `driver_location` | string | City or coordinates |
| `hos_hours_remaining` | number | Hours left on 11-hour driving limit |
| `load_number` | string | Freight load identifier |

Set the webhook URL to: `http://YOUR_BACKEND_URL/webhook/tool-call`

Add a second tool named `confirm_nav_yes_no` (the multi-turn gate — the fault
reply ends with "Ready to set nav — yes or no?" and the driver's answer
arrives here as a real turn through the `nav_confirm` graph branch):

| Parameter | Type | Description |
|---|---|---|
| `confirmed` | string | Driver answer: "yes" / "no" |
| `destination` | string | Shop name from the fault reply (optional, echoed back) |

Without this tool, the agent has nowhere to send the driver's "yes" and the
session just ends. With it, "yes" sets nav and "no" holds — see
`backend/agents/nav_confirm.py`.

## 5. Owned services (optional, HYBRID)

- **Owned STT**: `pip install faster-whisper` (pins `STT_MODEL=small.en`), then
  `POST /stt` with a 16 kHz WAV. Without the install the endpoint 503s with a
  hint — the ElevenLabs path is unaffected.
- **Owned LLM**: run Ollama locally (`ollama pull qwen2.5:3b`, serve on
  `OLLAMA_HOST`), set `PROVIDER_LLM=local`. Anthropic remains the fallback and
  the default; template-first replies never touch either backend.

## 6. Run Tests

Tests also run from the **repo root**, for the same import-path reason as the server:

```bash
python -m pytest backend/tests/ -v
```

111 tests (branch + STT + latency-relevant property coverage), all passing.

## 7. Running with Docker

See `backend/Dockerfile`, `frontend/Dockerfile`, and `docker-compose.yml` at
the repo root:

```bash
docker compose up --build
```

Backend on `http://localhost:8000`, frontend on `http://localhost:3000`.
`backend/.env` is required (see step 2); `docker-compose.yml` loads it via
`env_file`.

## CI

`.github/workflows/ci.yml` runs on every push/PR to `master`: backend tests
(`pytest backend/tests/`) and a frontend type-check + build. See that file
for the exact steps.
