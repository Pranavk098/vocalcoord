# backend/audit_log.py
"""Append-only audit trail: every SSE event, and the exact text spoken to the driver,
persisted to SQLite. Answers the "when a violation is contested, what did we say"
question raised in the audit's GTM section without pulling in Postgres/RBAC/retention
infra a demo doesn't need yet — same schema shape, easy to migrate once multi-fleet
tenancy is real.
"""
import json
import sqlite3
from pathlib import Path
from time import time

_DB_PATH = Path(__file__).parent / "data" / "audit_trail.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    ts REAL NOT NULL,
    event_type TEXT NOT NULL,
    data_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_conversation ON audit_events(conversation_id);
CREATE INDEX IF NOT EXISTS idx_audit_trace ON audit_events(trace_id);
"""

_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.executescript(_SCHEMA)
        _conn.commit()
    return _conn


def record(conversation_id: str, trace_id: str, event_type: str, data: dict) -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT INTO audit_events (conversation_id, trace_id, ts, event_type, data_json) VALUES (?, ?, ?, ?, ?)",
        (conversation_id, trace_id, time(), event_type, json.dumps(data, default=str)),
    )
    conn.commit()


def history_for_trace(trace_id: str) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT ts, event_type, data_json FROM audit_events WHERE trace_id = ? ORDER BY id",
        (trace_id,),
    ).fetchall()
    return [{"ts": ts, "type": t, "data": json.loads(d)} for ts, t, d in rows]
