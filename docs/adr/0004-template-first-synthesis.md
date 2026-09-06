# 0004. Template-first voice reply synthesis, LLM as fallback

## Status

Accepted

## Context

The final step of the pipeline turns agent findings (fault, shop, warranty,
dispatch, HOS status) into a single spoken voice reply. The common case —
all four agents resolved cleanly with no unusual state — produces
essentially the same reply shape every time: state the fault, summarize what
was arranged, ask for yes/no confirmation. Calling an LLM for every single
one of these adds a network round-trip's worth of latency and cost to the
majority path, for output that a fixed template can already produce
correctly and consistently.

This is also a safety-relevant surface: the exact phrasing of a fault
severity or warranty claim is read aloud to a driver who may act on it
immediately. A template removes hallucination risk from that phrasing
entirely for the common case.

## Decision

Render the voice reply from a fixed template for the common path — all
agents resolved, no ambiguity in fault/shop/warranty/dispatch/HOS state.
Reserve the LLM call for out-of-distribution states: unknown fault code, no
shop found, follow-up questions, or anything else the template set doesn't
cover.

The template path also serves as the degraded-mode fallback if the LLM call
times out or errors — the pipeline can still produce a correct, safe reply
without a working LLM connection.

## Consequences

- Cuts LLM latency (LangGraph's `response` node) and cost to near-zero on
  the majority of requests, since most fault responses hit the fully-resolved
  path.
- Removes hallucination risk on safety-relevant phrasing for the common
  case — the template's wording can be reviewed and tested like any other
  code path instead of trusted per-generation.
- Doubles as a resilience mechanism: an LLM outage degrades to
  template-only responses rather than failing the request outright.
- Adds a second reply-generation path to maintain — template and LLM output
  need to stay narratively consistent, and the "is this state covered by the
  template or does it need the LLM" boundary has to be kept accurate as new
  fault types and agent states are added.
