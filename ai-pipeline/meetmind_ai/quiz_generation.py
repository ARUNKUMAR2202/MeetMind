"""
Layer 4 — Quiz generation (Elkins et al., 2024 + Scaria et al., 2024), built on the
modular MCQ pipeline in mcq_pipeline.py (Bhowmick et al., 2023).

Scaria et al.'s core finding is that prompt design matters more than model size, and
that prompts naming the target Bloom's level explicitly with few-shot structure beat
generic instructions. We therefore run a separate question+answer generation call per
Bloom's level rather than one call asking for a mixed set — that's a direct,
deliberate application of their finding, not an implementation detail.

This is also MeetMind's highest-risk feature (see thesis Ch.5 "Peer Drilling" Q&A):
every reference paper tested quiz generation on clean written text, never on spoken
lecture transcripts. `flag_hallucinations` implements the evaluation methodology from
the thesis: a question is flagged if the evidence it cites can't actually be found in
the source transcript segment. Target: hallucination rate < 10% (settings.quiz_hallucination_target).
"""
from __future__ import annotations

from openai import OpenAI

from .config import settings
from .mcq_pipeline import build_mcq, filter_distractors, generate_distractors_batch, generate_question_and_answer_batch
from .schemas import ConceptSection, QuizQuestion

_BLOOM_LEVELS = ["remembering", "understanding", "applying"]


def generate_quiz(sections: list[ConceptSection], section_texts: dict[str, str]) -> list[QuizQuestion]:
    """
    section_texts maps a section title to the concatenated transcript text for that
    section (the pipeline builds this from the diarized/segmented transcript).

    Batched by section: ONE call generates all 3 Bloom's-level question+answer pairs,
    ONE call generates distractors for all 3 at once, then local quality filtering
    (mcq_pipeline.py) runs per-question with no further LLM calls — 2 calls per
    section instead of 6. See mcq_pipeline.py's batch functions for the fallback
    behavior if a batch response comes back malformed.
    """
    questions: list[QuizQuestion] = []

    for section in sections:
        excerpt = section_texts.get(section.title, section.summary)

        qa_items = generate_question_and_answer_batch(excerpt, _BLOOM_LEVELS)
        distractors_by_level = generate_distractors_batch(qa_items, excerpt)

        for qa in qa_items:
            level = qa["level"]
            raw_distractors = distractors_by_level.get(level, [])
            distractors = filter_distractors(raw_distractors, qa["correct_answer"])

            if len(distractors) < 2:
                # Quality filter rejected too many — regenerate once with a larger
                # over-generation budget for just this question, rather than
                # re-running the whole batch or shipping a 2-option question.
                from .mcq_pipeline import generate_distractors as _generate_distractors_single
                raw_distractors = _generate_distractors_single(
                    qa["question"], qa["correct_answer"], excerpt, count=6,
                )
                distractors = filter_distractors(raw_distractors, qa["correct_answer"])

            options, correct_index = build_mcq(qa["question"], qa["correct_answer"], distractors)

            questions.append(QuizQuestion(
                bloom_level=level,
                question=qa["question"],
                options=options,
                correct_index=correct_index,
                source_segment_start=section.start,
                source_segment_end=section.end,
                evidence_quote=qa.get("evidence_quote", ""),
            ))

    return questions


_HALLUCINATION_CHECK_PROMPT = """Source excerpt:
{excerpt}

Claimed evidence for a quiz question: "{evidence}"

Does the source excerpt actually support this claim? Answer with only one word: \
YES or NO."""


def flag_hallucinations(questions: list[QuizQuestion], section_texts: dict[str, str],
                         sections_by_span: dict[tuple, str]) -> int:
    """
    Implements the thesis's evaluation methodology (Ch.5): a question is flagged if its
    evidence_quote isn't actually supported by the source transcript excerpt. The thesis
    calls for 3 independent human evaluators and flags at 2/3 disagreement — this
    function is the automated first pass an evaluator would sanity-check, not a
    replacement for the human evaluation step.
    """
    settings.require_openai()
    client = OpenAI(api_key=settings.openai_api_key)
    flagged = 0

    for q in questions:
        excerpt = sections_by_span.get((q.source_segment_start, q.source_segment_end), "")
        if not excerpt or not q.evidence_quote:
            flagged += 1
            continue
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{
                "role": "user",
                "content": _HALLUCINATION_CHECK_PROMPT.format(excerpt=excerpt, evidence=q.evidence_quote),
            }],
            temperature=0,
        )
        if resp.choices[0].message.content.strip().upper().startswith("NO"):
            flagged += 1

    return flagged
