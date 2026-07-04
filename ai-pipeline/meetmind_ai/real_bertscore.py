"""
Optional REAL BERTScore (vs. action_items.py's confidence-weighted proxy). This is
what actually lets you compare against Golia & Kalita (2023)'s reported 64.98 on AMI —
the proxy function is just a placeholder number, never a real metric.

Kept separate because `bert-score` pulls in `transformers` + a pretrained scoring model
(roberta-large by default) — a real download + real compute cost not needed for the
mock-mode demo or for local dev without a reference summary to score against.

Setup:
  1. pip install -r requirements-real-bertscore.txt   (from ai-pipeline/)
  2. Set USE_REAL_BERTSCORE=true in backend/.env
  3. You need a REFERENCE summary to score against (e.g. a human-written action-item
     list for the same meeting, or the AMI test set's gold summaries per the thesis's
     evaluation plan) — BERTScore compares a candidate against a reference, it isn't
     a standalone quality score.

HONESTY NOTE: not run in this codebase's development environment — the sandbox that
built this has no network access to download the scoring model's weights. This is
the #2 item in TASK_SPLIT.md's AI-pipeline checklist for exactly that reason.
"""
from __future__ import annotations

from .schemas import ActionItem


def real_bertscore(candidate_items: list[ActionItem], reference_text: str) -> float:
    """
    Flattens the candidate action items into text and scores against `reference_text`
    (a human-written or gold-standard action-item summary for the same meeting).
    Returns the F1 component of BERTScore, 0-100 scale to match the thesis's 64.98
    target (bert_score.score returns 0-1; we multiply by 100 for a directly comparable
    number).
    """
    if not candidate_items:
        return 0.0

    try:
        from bert_score import score
    except ImportError as exc:
        raise RuntimeError(
            "bert-score isn't installed. Run `pip install -r "
            "requirements-real-bertscore.txt` from ai-pipeline/ first."
        ) from exc

    candidate_text = " ".join(f"{item.owner}: {item.task}" for item in candidate_items)
    _, _, f1 = score([candidate_text], [reference_text], lang="en", verbose=False)
    return round(float(f1[0]) * 100, 2)
