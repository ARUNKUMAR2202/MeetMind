
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
