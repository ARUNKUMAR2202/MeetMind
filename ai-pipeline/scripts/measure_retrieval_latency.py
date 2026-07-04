#!/usr/bin/env python3
"""
Retrieval latency evaluation harness — implements the thesis's Chapter 5 evaluation
plan: "Document Retrieval: Latency measured from spoken reference detection to
document surface in participant interface. Tested across 50 meeting sessions.
Target: consistently < 2 seconds."

This script provides the MEASUREMENT infrastructure; it does not manufacture the 50
real sessions the thesis calls for — you need real transcripts and real indexed
documents for the numbers to mean anything. Two ways to use it:

1. Against real data you already have (recommended once available):
     python scripts/measure_retrieval_latency.py --session-ids-file sessions.txt
   where sessions.txt has one session_id per line, and each session already has
   documents indexed via rag.index_document (e.g. through the running app).

2. Synthetic smoke-test (no real API calls) to sanity-check the harness itself:
     python scripts/measure_retrieval_latency.py --synthetic --count 50

Requires OPENAI_API_KEY and PINECONE_API_KEY in the environment for real mode
(reads the same .env as the rest of the app via meetmind_ai.config).
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meetmind_ai.config import settings
from meetmind_ai.schemas import Transcript, TranscriptSegment

TARGET_SECONDS = settings.retrieval_latency_target_seconds  # 2.0, from config.py


@dataclass
class LatencyResult:
    session_id: str
    latency_seconds: float
    matched: bool


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = min(len(sorted_vals) - 1, int(len(sorted_vals) * pct))
    return sorted_vals[idx]


def summarize(results: list[LatencyResult]) -> None:
    latencies = [r.latency_seconds for r in results]
    match_rate = sum(1 for r in results if r.matched) / len(results) if results else 0.0
    over_target = [l for l in latencies if l >= TARGET_SECONDS]

    print(f"\n{'='*60}")
    print(f"Retrieval latency report — {len(results)} queries")
    print(f"{'='*60}")
    print(f"  Target (thesis Ch.5):     < {TARGET_SECONDS:.1f}s")
    print(f"  Mean latency:             {statistics.mean(latencies):.3f}s" if latencies else "  No data")
    print(f"  Median (p50):             {_percentile(latencies, 0.50):.3f}s")
    print(f"  p90:                      {_percentile(latencies, 0.90):.3f}s")
    print(f"  p99:                      {_percentile(latencies, 0.99):.3f}s")
    print(f"  Max:                      {max(latencies):.3f}s" if latencies else "")
    print(f"  Queries over target:      {len(over_target)}/{len(results)}")
    print(f"  Document match rate:      {match_rate:.1%}")
    verdict = "PASS" if not over_target else "FAIL"
    print(f"  Verdict:                  {verdict} (target requires consistently < {TARGET_SECONDS}s)")
    print(f"{'='*60}\n")

    if len(results) < 50:
        print(
            f"NOTE: thesis Ch.5 calls for 50 sessions; this run only measured "
            f"{len(results)}. Treat this as a preliminary check, not the final number."
        )


def run_synthetic(count: int) -> list[LatencyResult]:
    """
    No network calls — just proves the measurement/reporting logic is correct, using
    a fake latency distribution. Useful for CI or a quick sanity check of this script
    itself; NOT a substitute for testing against real Pinecone + real sessions.
    """
    import random
    random.seed(42)
    results = []
    for i in range(count):
        # Simulate a realistic-ish distribution: mostly fast, occasional slow outlier.
        latency = abs(random.gauss(0.6, 0.3))
        if random.random() < 0.05:
            latency += random.uniform(1.5, 3.0)  # occasional slow tail
        results.append(LatencyResult(session_id=f"synthetic-{i}", latency_seconds=latency, matched=True))
    return results


def run_real(session_ids: list[str]) -> list[LatencyResult]:
    from meetmind_ai.rag import retrieve_for_mention

    results = []
    for session_id in session_ids:
        # In real use you'd load the actual transcript for this session (e.g. from
        # the backend's DB) — this is a placeholder single-segment transcript so the
        # script is runnable standalone. Replace `transcript` with your real one.
        transcript = Transcript(
            session_id=session_id,
            segments=[TranscriptSegment(start=0.0, end=5.0, text="Let's look at the Q3 roadmap document.")],
            raw_text="Let's look at the Q3 roadmap document.",
        )
        matches, latency = retrieve_for_mention(session_id, transcript, at_timestamp=5.0)
        results.append(LatencyResult(
            session_id=session_id, latency_seconds=latency, matched=len(matches) > 0,
        ))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-ids-file", type=str, help="File with one session_id per line")
    parser.add_argument("--synthetic", action="store_true", help="Run a fake-data smoke test instead")
    parser.add_argument("--count", type=int, default=50, help="Number of synthetic queries (default 50)")
    args = parser.parse_args()

    if args.synthetic:
        results = run_synthetic(args.count)
    elif args.session_ids_file:
        session_ids = [line.strip() for line in Path(args.session_ids_file).read_text().splitlines() if line.strip()]
        settings.require_openai()
        settings.require_pinecone()
        results = run_real(session_ids)
    else:
        parser.error("Pass either --synthetic or --session-ids-file")
        return

    summarize(results)


if __name__ == "__main__":
    main()
