# 0002. Deterministic Python lookups, not LLM tool-calls, for fault/shop/warranty data

## Status

Accepted

## Context

Shop selection, warranty coverage, and fault-code decoding (`backend/tools/
j1939.py`, `shop_db.py`, `warranty_db.py`) all read from static JSON and
apply plain Python logic — table lookups, filtering, ranking. None of these
go through the LLM as a tool call. The LLM (`backend/agents/response.py`) is
only invoked once, at the very end of the pipeline, to turn already-computed
agent findings into a natural-language voice reply.

This is a safety-adjacent product: a driver is being told whether a fault is
safe to keep driving on, whether a shop has the part in stock, and whether a
repair is covered under warranty, while behind the wheel. An LLM asked to
"look up the warranty coverage for SPN 4334" can hallucinate a plausible but
wrong coverage code or claim value with no way to tell from the output alone.

## Decision

Fault decoding, shop search, and warranty lookups are deterministic Python
functions over local JSON data. The LLM is confined to final natural-language
synthesis of results that were already computed deterministically — it never
originates a fact, only phrases one.

## Consequences

- Every number or claim in a voice reply (fault severity, shop distance,
  warranty claim value, HOS status) traces back to a JSON lookup or a plain
  function, not a model generation — this keeps the audit trail testable and
  the JSON fixtures (`backend/data/`) reviewable by non-engineers.
- `backend/tests/` can assert exact expected values for lookups without
  needing to tolerate LLM output variance.
- The LLM call itself is a single, narrow surface (one prompt, one output
  string per request), which keeps hallucination risk scoped to phrasing
  rather than facts.
- This trades away flexibility: swapping in a smarter fuzzy-matched shop
  search or a richer warranty reasoning step means writing more deterministic
  logic, not just improving a prompt.
