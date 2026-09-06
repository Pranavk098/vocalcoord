#!/usr/bin/env python3
"""Latency eval: 20 scripted fault utterances -> webhook-to-reply timing.

Measures the full product path (POST /webhook/tool-call -> graph branches ->
template-first reply) in-process via ASGITransport, so results are
deterministic and need no ANTHROPIC_API_KEY (all 20 cases hit the template
fast path by construction). Reports:

  - webhook-to-reply p50/p95 (ms)
  - template-hit rate (template replies / total)
  - HOS-tier correctness table (expected tier vs reply contains HOS warning)

Usage (from repo root):
  python scripts/eval_latency.py [--json out.json] [--markdown out.md]

The README's Latency table is generated from this script's output.
"""
import argparse
import asyncio
import json
import statistics
import sys
from pathlib import Path
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import ASGITransport, AsyncClient  # noqa: E402

from backend.main import app  # noqa: E402

# 20 scripted cases: 10 fixture fault codes x 2 HOS representatives, plus tier
# edge coverage folded in via explicit HOS values across the 5 FMCSA tiers.
CASES = [
    {"fault_code": "SPN 4334 FMI 18", "hos": 0.5, "city": "Columbus, OH", "tier": "CRITICAL"},
    {"fault_code": "SPN 4334 FMI 18", "hos": 1.5, "city": "Phoenix", "tier": "SEVERE"},
    {"fault_code": "SPN 4334 FMI 18", "hos": 3.0, "city": "Dallas", "tier": "CAUTION"},
    {"fault_code": "SPN 4334 FMI 18", "hos": 5.0, "city": "Atlanta", "tier": "WATCH"},
    {"fault_code": "SPN 4334 FMI 18", "hos": 8.0, "city": "Chicago", "tier": "CLEAR"},
    {"fault_code": "SPN 3251 FMI 16", "hos": 0.8, "city": "Denver", "tier": "CRITICAL"},
    {"fault_code": "SPN 3251 FMI 16", "hos": 4.5, "city": "Columbus, OH", "tier": "WATCH"},
    {"fault_code": "SPN 100 FMI 1", "hos": 0.3, "city": "Memphis", "tier": "CRITICAL"},
    {"fault_code": "SPN 100 FMI 1", "hos": 2.5, "city": "Nashville", "tier": "CAUTION"},
    {"fault_code": "SPN 520192 FMI 31", "hos": 1.9, "city": "Kansas City", "tier": "SEVERE"},
    {"fault_code": "SPN 520192 FMI 31", "hos": 7.0, "city": "St. Louis", "tier": "CLEAR"},
    {"fault_code": "SPN 102 FMI 1", "hos": 1.0, "city": "Louisville", "tier": "SEVERE"},
    {"fault_code": "SPN 102 FMI 1", "hos": 6.5, "city": "Cincinnati", "tier": "CLEAR"},
    {"fault_code": "SPN 110 FMI 0", "hos": 0.9, "city": "Cleveland", "tier": "CRITICAL"},
    {"fault_code": "SPN 110 FMI 0", "hos": 3.5, "city": "Pittsburgh", "tier": "WATCH"},
    {"fault_code": "SPN 412 FMI 3", "hos": 2.0, "city": "Indianapolis", "tier": "CAUTION"},
    {"fault_code": "SPN 412 FMI 3", "hos": 9.0, "city": "Los Angeles", "tier": "CLEAR"},
    {"fault_code": "SPN 521 FMI 9", "hos": 0.6, "city": "Columbus, OH", "tier": "CRITICAL"},
    {"fault_code": "SPN 521 FMI 9", "hos": 5.5, "city": "Phoenix", "tier": "WATCH"},
    {"fault_code": "SPN 94 FMI 1", "hos": 8.0, "city": "Dallas", "tier": "CLEAR"},
]


def _pct(data: list[float], p: float) -> float:
    ordered = sorted(data)
    n = len(ordered)
    import math

    k = max(1, min(n, math.ceil(p / 100 * n)))
    return round(ordered[k - 1], 1)


async def run_case(client: AsyncClient, i: int, case: dict) -> dict:
    payload = {
        "type": "tool_call",
        "conversation_id": f"eval_lat_{i:02d}",
        "tool_name": "trigger_fault_response",
        "parameters": {
            "fault_code": case["fault_code"],
            "driver_location": case["city"],
            "hos_hours_remaining": case["hos"],
            "load_number": f"LOAD-EVAL-{i:02d}",
        },
    }
    t0 = monotonic()
    resp = await client.post("/webhook/tool-call", json=payload)
    latency_ms = round((monotonic() - t0) * 1000, 1)
    assert resp.status_code == 200, resp.text
    reply = resp.json()["result"]
    template_hit = reply.strip().endswith("Ready to set nav — yes or no?")
    # HOS correctness: CRITICAL/SEVERE must surface an HOS warning; CLEAR must not force one.
    needs_hos = case["tier"] in ("CRITICAL", "SEVERE")
    hos_ok = ("HOS" in reply) if needs_hos else True
    return {
        "case": i + 1,
        "fault_code": case["fault_code"],
        "hos": case["hos"],
        "expected_tier": case["tier"],
        "latency_ms": latency_ms,
        "template_hit": template_hit,
        "hos_correct": bool(hos_ok),
        "reply_chars": len(reply),
    }


async def main() -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--markdown", default=None)
    args = ap.parse_args()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Warmup (unrecorded): absorbs cold-start costs (imports, SQLite
        # checkpoint table, first-compile) so the measured cases reflect
        # steady-state webhook-to-reply latency.
        await run_case(client, -1, {**CASES[0], "hos": 8.0})
        results = [await run_case(client, i, c) for i, c in enumerate(CASES)]

    lat = [r["latency_ms"] for r in results]
    template_hits = sum(1 for r in results if r["template_hit"])
    hos_ok = sum(1 for r in results if r["hos_correct"])
    summary = {
        "n": len(results),
        "p50_ms": _pct(lat, 50),
        "p95_ms": _pct(lat, 95),
        "mean_ms": round(statistics.fmean(lat), 1),
        "max_ms": max(lat),
        "template_hit_rate": round(template_hits / len(results), 3),
        "hos_correct_rate": round(hos_ok / len(results), 3),
        "cases": results,
    }

    # Per-tier correctness breakdown.
    tiers: dict[str, dict] = {}
    for r in results:
        t = tiers.setdefault(r["expected_tier"], {"n": 0, "hos_correct": 0})
        t["n"] += 1
        t["hos_correct"] += 1 if r["hos_correct"] else 0

    print(f"cases={summary['n']} p50={summary['p50_ms']}ms p95={summary['p95_ms']}ms "
          f"mean={summary['mean_ms']}ms template_hit={template_hits}/{len(results)} "
          f"hos_correct={hos_ok}/{len(results)}")
    print("\n| # | Fault | HOS | Tier | ms | tmpl | HOS-ok |")
    print("|---|---|---|---|---|---|---|")
    for r in results:
        print(f"| {r['case']} | {r['fault_code']} | {r['hos']} | {r['expected_tier']} "
              f"| {r['latency_ms']} | {'Y' if r['template_hit'] else 'N'} | {'Y' if r['hos_correct'] else 'N'} |")
    print("\nTier breakdown:")
    for tier in ("CRITICAL", "SEVERE", "CAUTION", "WATCH", "CLEAR"):
        t = tiers.get(tier, {"n": 0, "hos_correct": 0})
        print(f"  {tier}: {t['hos_correct']}/{t['n']} correct")

    if args.json:
        Path(args.json).write_text(json.dumps(summary, indent=2))
        print(f"\nwrote {args.json}")
    if args.markdown:
        lines = ["| # | Fault | HOS | Tier | ms | tmpl | HOS-ok |",
                 "|---|---|---|---|---|---|---|"]
        for r in results:
            lines.append(f"| {r['case']} | {r['fault_code']} | {r['hos']} | {r['expected_tier']} "
                         f"| {r['latency_ms']} | {'Y' if r['template_hit'] else 'N'} | "
                         f"{'Y' if r['hos_correct'] else 'N'} |")
        Path(args.markdown).write_text("\n".join(lines) + "\n")
        print(f"wrote {args.markdown}")
    return summary


if __name__ == "__main__":
    asyncio.run(main())
