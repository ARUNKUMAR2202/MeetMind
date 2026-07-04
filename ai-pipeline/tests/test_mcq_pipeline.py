import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meetmind_ai.mcq_pipeline import build_mcq, filter_distractors
from meetmind_ai.schemas import ConceptSection


def test_filter_distractors_removes_duplicate_of_correct_answer():
    result = filter_distractors(
        distractors=["Paris", "Berlin", "paris", "Madrid"],
        correct_answer="Paris",
    )
    assert "Paris" not in [d for d in result]  # exact/case-insensitive dupes of the answer are gone
    assert "Berlin" in result
    assert "Madrid" in result


def test_filter_distractors_removes_repeats_of_each_other():
    result = filter_distractors(
        distractors=["Berlin", "berlin", "BERLIN", "Madrid"],
        correct_answer="Paris",
    )
    assert result.count("Berlin") + result.count("berlin") + result.count("BERLIN") == 1
    assert "Madrid" in result


def test_filter_distractors_rejects_implausible_lengths():
    result = filter_distractors(
        distractors=["x", "Berlin", "This is a wildly overlong distractor compared to the answer length here"],
        correct_answer="Paris",
    )
    assert "x" not in result  # too short relative to "Paris"
    assert "Berlin" in result


def test_filter_distractors_caps_at_target_count():
    result = filter_distractors(
        distractors=["Berlin", "Madrid", "Rome", "Tokyo", "Cairo"],
        correct_answer="Paris",
        target_count=3,
    )
    assert len(result) == 3


def test_build_mcq_places_correct_answer_and_returns_valid_index():
    options, correct_index = build_mcq("Q?", "Paris", ["Berlin", "Madrid", "Rome"])
    assert len(options) == 4
    assert options[correct_index] == "Paris"
    assert set(options) == {"Paris", "Berlin", "Madrid", "Rome"}


@patch("meetmind_ai.quiz_generation.generate_distractors_batch")
@patch("meetmind_ai.quiz_generation.generate_question_and_answer_batch")
def test_generate_quiz_produces_one_question_per_bloom_level(mock_qa_batch, mock_distractors_batch):
    from meetmind_ai import quiz_generation

    mock_qa_batch.return_value = [
        {"level": level, "question": "What did the team decide?",
         "correct_answer": "Ship Friday", "evidence_quote": "the team agreed to ship on Friday"}
        for level in ("remembering", "understanding", "applying")
    ]
    mock_distractors_batch.return_value = {
        level: ["Ship Monday", "Cancel the release", "Delay a month"]
        for level in ("remembering", "understanding", "applying")
    }

    sections = [ConceptSection(
        title="Planning", start=0.0, end=10.0,
        summary="The team planned the release.", key_concepts=["release planning"],
    )]
    section_texts = {"Planning": "We agreed to ship on Friday after testing."}

    questions = quiz_generation.generate_quiz(sections, section_texts)

    assert len(questions) == 3  # one per Bloom's level
    levels = {q.bloom_level for q in questions}
    assert levels == {"remembering", "understanding", "applying"}
    # Batched: exactly one QA call and one distractor call per section, not one per level.
    assert mock_qa_batch.call_count == 1
    assert mock_distractors_batch.call_count == 1
    for q in questions:
        assert len(q.options) == 4
        assert q.options[q.correct_index] == "Ship Friday"


@patch("meetmind_ai.mcq_pipeline.generate_distractors")
@patch("meetmind_ai.quiz_generation.generate_distractors_batch")
@patch("meetmind_ai.quiz_generation.generate_question_and_answer_batch")
def test_generate_quiz_retries_distractors_when_filter_rejects_too_many(
    mock_qa_batch, mock_distractors_batch, mock_single_distractor_fallback,
):
    from meetmind_ai import quiz_generation

    levels = ("remembering", "understanding", "applying")
    mock_qa_batch.return_value = [
        {"level": level, "question": "What did the team decide?",
         "correct_answer": "Ship Friday", "evidence_quote": "shipped Friday"}
        for level in levels
    ]
    # The batch distractor call returns only near-duplicates of the correct answer for
    # every level — the quality filter should reject nearly all of them, triggering the
    # single-question fallback retry (mcq_pipeline.generate_distractors) for each one.
    mock_distractors_batch.return_value = {
        level: ["Ship Friday", "ship friday", "SHIP FRIDAY"] for level in levels
    }
    mock_single_distractor_fallback.return_value = ["Ship Monday", "Cancel release", "Delay launch", "Push to Q3"]

    sections = [ConceptSection(title="Planning", start=0.0, end=10.0, summary="s", key_concepts=[])]
    questions = quiz_generation.generate_quiz(sections, {"Planning": "text"})

    assert mock_single_distractor_fallback.call_count == 3  # one retry per bloom level
    for q in questions:
        assert len(q.options) >= 3  # retry rescued the question rather than shipping 2 options
