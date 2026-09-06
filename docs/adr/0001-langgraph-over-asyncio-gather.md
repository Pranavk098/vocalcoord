# 0001. LangGraph StateGraph over plain asyncio.gather

## Status

Accepted

## Context

The core orchestration flow is two steps: classify the driver's intent and
route to the relevant agents (`orchestrator`), then synthesize their findings
into a single voice reply (`response`). As implemented today
(`backend/graph.py`), this is a linear two-node graph — orchestrator feeds
directly into response, no branching, no cycles. The agent fan-out inside the
orchestrator node (shop caller, warranty scout, wellness co-pilot, dispatch
relay) is itself already done with plain `asyncio.gather`, not graph edges.

A two-node linear pipeline like this could be written as a single async
function that calls `orchestrate()` then `build_voice_reply()` — no graph
library required.

## Decision

Use LangGraph's `StateGraph` to define the orchestrator → response flow,
even though today's graph is thin enough that `asyncio.gather` plus a plain
function call would do the same job with less code and one fewer dependency.

We're choosing it for where this goes next, not what it is today: intent
classification is expected to grow into real branching (different node paths
per intent instead of one node routing internally), we expect to add
retry/checkpoint nodes around flaky external calls, and LangGraph gives us
graph visualization and tracing for free as the pipeline grows.

## Consequences

- Today's graph is arguably over-engineered for its size — this is an
  accepted tradeoff, not an oversight. A reviewer skimming `graph.py` will
  reasonably ask "why not just call two functions?"
- We inherit LangGraph's dependency surface (and its release cadence) before
  we're using most of its feature set.
- The state shape (`VocalCoordState`) is already a `TypedDict` threaded
  through the graph, which makes it cheap to add nodes later without
  reshaping the state contract.
- If the graph doesn't grow branches/retries within a reasonable timeframe,
  this decision should be revisited — collapsing back to a plain function
  call is a small change while the graph is still this simple.
