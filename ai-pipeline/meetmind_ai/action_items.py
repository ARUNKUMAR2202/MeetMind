"""
Layer 5 — Action-item extraction (Golia & Kalita, 2023).

The paper's approach is topic-segmentation + a fine-tuned BART model scoring
BERTScore 64.98 on AMI. We don't have a fine-tuned BART checkpoint in this starter, so
we approximate the same task with a structured LLM extraction prompt. If/when the team
fine-tunes or hosts the actual BART model from the paper, swap the body of
`extract_action_items` for a call to that model — the function signature (transcript
in, list[ActionItem] out) shouldn't need to change.

`estimate_bertscore_proxy` is NOT a real BERTScore implementation — it's a lightweight
placeholder so the pipeline can report *something* against the thesis's target metric
without needing a reference summary. For a real score, use `score_action_items(...)`
with `reference_text` set and USE_REAL_BERTSCORE=true (see real_bertscore.py) — you'll
need gold reference summaries from the AMI test set or similar (thesis Ch.5,
Evaluation Approach).
"""
from __future__ import annotations

import json

from openai import OpenAI

from .config import settings
from .schemas import ActionItem, Transcript

_EXTRACTION_PROMPT = """Extract every action item (task someone committed to or was \
assigned) from this meeting transcript. Only extract items with a clear owner and task \
— do not invent tasks that weren't actually said.

Transcript (each line is "[start-end] speaker: text"):
{lines}

Return ONLY a JSON object: {{"action_items": [{{"owner": string, "task": string, \
"due": string or null, "source_segment_start": number, "source_segment_end": number, \
"confidence": 0-1}}]}}"""


def extract_action_items(transcript: Transcript) -> list[ActionItem]:
    settings.require_openai()
    client = OpenAI(api_key=settings.openai_api_key)
    lines = "\n".join(
        f"[{s.start:.1f}-{s.end:.1f}] {s.speaker or 'Unknown'}: {s.text}"
        for s in transcript.segments
    )
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": _EXTRACTION_PROMPT.format(lines=lines)}],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    return [ActionItem(**item) for item in data.get("action_items", [])]


def estimate_bertscore_proxy(action_items: list[ActionItem]) -> float:
    """Placeholder metric — see module docstring. Replace before citing this number anywhere real."""
    if not action_items:
        return 0.0
    avg_confidence = sum(a.confidence for a in action_items) / len(action_items)
    return round(avg_confidence * settings.action_item_bertscore_target, 2)


def score_action_items(action_items: list[ActionItem], reference_text: str | None = None) -> float:
    """
    Routing entry point, same pattern as diarization.diarize(): uses the real
    BERTScore backend (real_bertscore.py) when USE_REAL_BERTSCORE is set AND a
    reference summary is available to score against — BERTScore is inherently a
    comparison metric, so without a reference there's nothing real to compute, and we
    fall back to the confidence-weighted proxy instead of raising.
    """
    if settings.use_real_bertscore and reference_text:
        from .real_bertscore import real_bertscore
        return real_bertscore(action_items, reference_text)
    return estimate_bertscore_proxy(action_items)
