#!/usr/bin/env python3
"""
Helps calibrate config.py's `noise_threshold` (currently a guess — see that file's
comment) against real recordings, once you have some. The threshold decides whether
Tan et al. (2023)'s RPB preprocessing step runs before summarization — too low and
you're paying the extra LLM-call cost/latency on clean audio for no benefit; too high
and genuinely noisy transcripts skip cleanup they need.

Usage:
  1. Transcribe a handful of real recordings (a few clean, a few genuinely noisy —
     background chatter, cross-talk, mumbling) using the normal pipeline, OR reuse
     transcripts you already have from real sessions.
  2. Label each one "clean" or "noisy" by ear/eye — a human judgment call, that's the
     point of calibration.
  3. Run: python scripts/calibrate_noise_threshold.py --clean clean1.txt clean2.txt
          --noisy noisy1.txt noisy2.txt
     (each file should contain the raw transcript text, one utterance doesn't matter —
     estimate_noise_score works on the whole raw_text string)
  4. The script reports the noise_score distribution for each group and suggests a
     threshold that separates them — sanity-check it against your own judgment before
     changing config.py.

This does NOT require any API keys — estimate_noise_score is a local heuristic
(filler-word + repetition ratio), not an LLM call.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meetmind_ai.transcription import estimate_noise_score


def _load_texts(paths: list[str]) -> list[str]:
    return [Path(p).read_text() for p in paths]


def _report_group(label: str, texts: list[str]) -> list[float]:
    scores = [estimate_noise_score(t) for t in texts]
    if scores:
        print(f"{label} (n={len(scores)}):")
        print(f"  scores: {[round(s, 3) for s in scores]}")
        print(f"  mean:   {statistics.mean(scores):.3f}")
        print(f"  min/max: {min(scores):.3f} / {max(scores):.3f}")
    else:
        print(f"{label}: no files provided")
    return scores


def suggest_threshold(clean_scores: list[float], noisy_scores: list[float]) -> None:
    if not clean_scores or not noisy_scores:
        print("\nNeed at least one file in both --clean and --noisy to suggest a threshold.")
        return

    # Simplest reasonable midpoint: halfway between the noisiest "clean" sample and
    # the cleanest "noisy" sample. Flags a warning if the groups overlap — that means
    # noise_score isn't cleanly separating your samples and the heuristic itself may
    # need work, not just the threshold value.
    max_clean = max(clean_scores)
    min_noisy = min(noisy_scores)

    print(f"\n{'='*60}")
    if max_clean < min_noisy:
        suggested = round((max_clean + min_noisy) / 2, 3)
        print(f"Groups are cleanly separated. Suggested noise_threshold: {suggested}")
        print(f"(currently {_current_threshold()} in config.py)")
    else:
        print("WARNING: your 'clean' and 'noisy' groups OVERLAP in noise_score —")
        print(f"  noisiest clean sample:  {max_clean:.3f}")
        print(f"  cleanest noisy sample:  {min_noisy:.3f}")
        print("This means the heuristic (filler-word + repetition ratio) isn't")
        print("cleanly distinguishing your samples. Consider more samples, or revisit")
        print("estimate_noise_score's approach in transcription.py before trusting a")
        print("threshold picked from this data.")
    print(f"{'='*60}\n")


def _current_threshold() -> float:
    from meetmind_ai.config import settings
    return settings.noise_threshold


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clean", nargs="*", default=[], help="Paths to transcripts judged clean/well-spoken")
    parser.add_argument("--noisy", nargs="*", default=[], help="Paths to transcripts judged noisy/disfluent")
    args = parser.parse_args()

    if not args.clean and not args.noisy:
        parser.error("Provide at least --clean and/or --noisy transcript files")

    clean_scores = _report_group("Clean", _load_texts(args.clean))
    noisy_scores = _report_group("Noisy", _load_texts(args.noisy))
    suggest_threshold(clean_scores, noisy_scores)


if __name__ == "__main__":
    main()
