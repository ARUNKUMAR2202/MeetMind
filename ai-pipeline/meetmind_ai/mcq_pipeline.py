"""
Modular MCQ pipeline (Bhowmick et al., 2023, "Automating question generation from
educational text"). The paper's contribution is specifically the *separation* of
concerns — question+answer generation, distractor generation, and quality filtering
as independent, swappable stages, rather than one model asked to produce a whole
multiple-choice item at once. This module implements that structure literally, so it's
the piece to swap if you want to try a different distractor strategy or add the
paper's domain-adaptation step without touching quiz_generation.py's Bloom's-level
orchestration.

Quality filtering here is a fast local heuristic (no LLM call) — the paper's own
filtering step is also non-generative (a classifier over candidate distractors), so
this is faithful to the architecture even though the specific filter is simpler.
"""
from __future__ import annotations

import json
import random

from openai import OpenAI

from .config import settings

_QA_PROMPT = """Write ONE question at the "{level}" level of Bloom's taxonomy, grounded \
ONLY in the excerpt below, plus its single correct answer. Do not invent facts not \
present in the excerpt.

Bloom's level guidance:
- remembering: recall a fact or term stated directly
- understanding: explain or paraphrase an idea from the excerpt
- applying: use a concept from the excerpt in a new but concrete scenario

Excerpt:
{text}

Return ONLY a JSON object:
{{"question": string, "correct_answer": string (short — a phrase, not a sentence), \
"evidence_quote": "short paraphrase (not a direct quote) of the part of the excerpt \
that supports the answer"}}"""

_QA_BATCH_PROMPT = """Write ONE question for EACH of the following Bloom's taxonomy \
levels, all grounded ONLY in the excerpt below. Do not invent facts not present in \
the excerpt.

Levels needed: {levels}

Bloom's level guidance:
- remembering: recall a fact or term stated directly
- understanding: explain or paraphrase an idea from the excerpt
- applying: use a concept from the excerpt in a new but concrete scenario

Excerpt:
{text}

Return ONLY a JSON object: {{"items": [{{"level": string (one of {levels}), \
"question": string, "correct_answer": string (short — a phrase, not a sentence), \
"evidence_quote": "short paraphrase (not a direct quote) of the part of the excerpt \
that supports the answer"}}, ... one entry per level, same order as listed above]}}"""

_DISTRACTOR_PROMPT = """Question: {question}
Correct answer: {correct_answer}
Source excerpt: {text}

Write {count} plausible but WRONG answers (distractors) for this question. Each should:
- be the same style/length/grammatical form as the correct answer
- be plausible enough that someone who skimmed the excerpt might pick it
- be clearly wrong to someone who understood the excerpt
- NOT be a paraphrase of the correct answer

Return ONLY a JSON object: {{"distractors": [{count} strings]}}"""

_DISTRACTOR_BATCH_PROMPT = """Source excerpt: {text}

For EACH question below, write {count} plausible but WRONG answers (distractors). Each \
distractor should be the same style/length as that question's correct answer, plausible \
enough that someone who skimmed the excerpt might pick it, clearly wrong to someone who \
understood the excerpt, and NOT a paraphrase of the correct answer.

Questions:
{questions_block}

Return ONLY a JSON object: {{"items": [{{"level": string, "distractors": [{count} \
strings]}}, ... one entry per question above, same order, matched by "level"]}}"""


def generate_question_and_answer_batch(excerpt: str, levels: list[str]) -> list[dict]:
    """
    One LLM call producing a question+answer for every Bloom's level at once, instead
    of one call per level. Falls back to per-level results if the batch response is
    malformed (missing/extra levels) — quiz quality matters more than call count.
    """
    settings.require_openai()
    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{
            "role": "user",
            "content": _QA_BATCH_PROMPT.format(levels=levels, text=excerpt),
        }],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    items = data.get("items", [])

    # Defensive: if the model dropped or duplicated a level, fill gaps with individual
    # calls rather than silently shipping fewer questions than requested.
    by_level = {item["level"]: item for item in items if item.get("level") in levels}
    for level in levels:
        if level not in by_level:
            by_level[level] = {"level": level, **generate_question_and_answer(excerpt, level)}

    return [by_level[level] for level in levels]


def generate_distractors_batch(qa_items: list[dict], excerpt: str, count: int = 4) -> dict[str, list[str]]:
    """
    One LLM call generating distractors for every question at once. Returns a dict
    keyed by Bloom's level (matching qa_items' "level" field) so the caller doesn't
    need to worry about ordering.
    """
    settings.require_openai()
    client = OpenAI(api_key=settings.openai_api_key)
    questions_block = "\n".join(
        f'- level="{item["level"]}": Q: {item["question"]} | Correct answer: {item["correct_answer"]}'
        for item in qa_items
    )
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{
            "role": "user",
            "content": _DISTRACTOR_BATCH_PROMPT.format(text=excerpt, questions_block=questions_block, count=count),
        }],
        temperature=0.6,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    result = {item["level"]: item.get("distractors", []) for item in data.get("items", [])}

    # Defensive fallback per question, same rationale as the QA batch above.
    for item in qa_items:
        if item["level"] not in result:
            result[item["level"]] = generate_distractors(item["question"], item["correct_answer"], excerpt, count)

    return result


def generate_question_and_answer(excerpt: str, level: str) -> dict:
    settings.require_openai()
    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": _QA_PROMPT.format(level=level, text=excerpt)}],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def generate_distractors(question: str, correct_answer: str, excerpt: str, count: int = 4) -> list[str]:
    """Over-generates slightly (default 4, need 3 after filtering) to survive quality filtering."""
    settings.require_openai()
    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{
            "role": "user",
            "content": _DISTRACTOR_PROMPT.format(
                question=question, correct_answer=correct_answer, text=excerpt, count=count,
            ),
        }],
        temperature=0.6,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    return data.get("distractors", [])


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def filter_distractors(distractors: list[str], correct_answer: str, target_count: int = 3) -> list[str]:
    """
    Local quality filter — no LLM call. Removes distractors that are:
      - near-duplicates of the correct answer (would make the question unanswerable)
      - near-duplicates of each other
      - implausibly short/long relative to the correct answer (obvious tell)
    Returns at most `target_count` distractors; may return fewer if too many were
    filtered out — callers should handle a final option count of 3 gracefully.
    """
    correct_norm = _normalize(correct_answer)
    correct_len = max(len(correct_answer), 1)

    seen: set[str] = set()
    kept: list[str] = []

    for d in distractors:
        norm = _normalize(d)
        if not norm or norm == correct_norm:
            continue
        if norm in seen:
            continue
        # Reject wildly different length (a common LLM tell for the "obviously wrong" option)
        length_ratio = len(d) / correct_len
        if length_ratio < 0.3 or length_ratio > 3.0:
            continue
        seen.add(norm)
        kept.append(d.strip())
        if len(kept) == target_count:
            break

    return kept


def build_mcq(question: str, correct_answer: str, distractors: list[str]) -> tuple[list[str], int]:
    """Shuffles correct answer among distractors. Returns (options, correct_index)."""
    options = distractors + [correct_answer]
    random.shuffle(options)
    return options, options.index(correct_answer)
