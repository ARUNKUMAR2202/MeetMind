"""
Runs entirely offline — every OpenAI/Pinecone call is monkeypatched. This is what CI
should run on every PR. It does NOT replace real-audio testing against your own API
keys (see README "Running against real audio").
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meetmind_ai.diarization import diarize, heuristic_diarize, needs_overlap_fallback
from meetmind_ai.schemas import Transcript, TranscriptSegment
from meetmind_ai.transcription import estimate_noise_score


def _sample_transcript() -> Transcript:
    return Transcript(
        session_id="test-session",
        segments=[
            TranscriptSegment(start=0.0, end=2.0, text="Let's start the standup."),
            TranscriptSegment(start=2.1, end=4.0, text="I finished the API yesterday."),
            TranscriptSegment(start=5.5, end=7.0, text="Great, can you send the report by Friday?"),
        ],
        raw_text="Let's start the standup. I finished the API yesterday. Great, can you send the report by Friday?",
    )


def test_noise_score_detects_fillers():
    clean = "We agreed to ship the feature on Monday."
    noisy = "um so like we uh agreed to um ship the the feature you know on Monday"
    assert estimate_noise_score(clean) < estimate_noise_score(noisy)


def test_heuristic_diarize_assigns_alternating_speakers_on_pause():
    transcript = _sample_transcript()
    result = diarize(transcript, diarizer=heuristic_diarize)
    speakers = [s.speaker for s in result.segments]
    # third segment has a >0.6s gap from the second -> should be a new speaker
    assert speakers[0] == speakers[1]
    assert speakers[1] != speakers[2]


def test_needs_overlap_fallback_false_for_sequential_segments():
    transcript = _sample_transcript()
    assert needs_overlap_fallback(transcript) is False


def test_needs_overlap_fallback_true_when_segments_overlap():
    transcript = Transcript(
        session_id="overlap-test",
        segments=[
            TranscriptSegment(start=0.0, end=3.0, text="I think we should—"),
            TranscriptSegment(start=1.5, end=4.0, text="—wait, let me finish"),
            TranscriptSegment(start=2.0, end=5.0, text="sorry go ahead"),
        ],
        raw_text="",
    )
    assert needs_overlap_fallback(transcript, overlap_ratio_threshold=0.2) is True


@patch("meetmind_ai.action_items.settings")
@patch("meetmind_ai.action_items.OpenAI")
def test_extract_action_items_parses_llm_json(mock_openai_cls, mock_settings):
    from meetmind_ai import action_items

    mock_settings.require_openai.return_value = None
    mock_settings.openai_api_key = "test-key"
    mock_settings.llm_model = "gpt-4o"

    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        '{"action_items": [{"owner": "Raj", "task": "Send the report", '
        '"due": "Friday", "source_segment_start": 5.5, "source_segment_end": 7.0, '
        '"confidence": 0.9}]}'
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_cls.return_value = mock_client

    transcript = _sample_transcript()
    result = action_items.extract_action_items(transcript)

    assert len(result) == 1
    assert result[0].owner == "Raj"
    assert result[0].task == "Send the report"


@patch("meetmind_ai.action_items.OpenAI")
def test_bertscore_proxy_scales_with_confidence(mock_openai_cls):
    from meetmind_ai import action_items
    from meetmind_ai.schemas import ActionItem

    items = [
        ActionItem(owner="A", task="x", source_segment_start=0, source_segment_end=1, confidence=1.0),
    ]
    score = action_items.estimate_bertscore_proxy(items)
    assert score == 64.98  # full confidence -> hits the paper's target exactly

    low_conf_items = [
        ActionItem(owner="A", task="x", source_segment_start=0, source_segment_end=1, confidence=0.5),
    ]
    low_score = action_items.estimate_bertscore_proxy(low_conf_items)
    assert low_score < score


def test_filter_distractors_removes_duplicate_of_correct_answer():
    from meetmind_ai.mcq_pipeline import filter_distractors

    kept = filter_distractors(
        ["Paris", "paris", "London", "Berlin", "Madrid"], correct_answer="Paris",
    )
    assert "Paris" not in [k for k in kept]
    assert "paris" not in [k.lower() for k in kept if k.lower() == "paris"]
    # exact/case-insensitive duplicate of the correct answer must be gone
    assert all(k.strip().lower() != "paris" for k in kept)


def test_filter_distractors_removes_length_outliers():
    from meetmind_ai.mcq_pipeline import filter_distractors

    kept = filter_distractors(
        ["Reasonable length answer", "x", "Another reasonable one", "A" * 500],
        correct_answer="A normal length answer",
        target_count=5,
    )
    assert "x" not in kept
    assert "A" * 500 not in kept


def test_filter_distractors_dedupes_near_identical_options():
    from meetmind_ai.mcq_pipeline import filter_distractors

    kept = filter_distractors(
        ["The mitochondria", "the   mitochondria", "The nucleus"],
        correct_answer="The ribosome",
    )
    assert len(kept) == 2  # the two mitochondria variants collapse to one


def test_build_mcq_places_correct_answer_among_options():
    from meetmind_ai.mcq_pipeline import build_mcq

    options, correct_index = build_mcq("What is X?", "the right one", ["wrong 1", "wrong 2", "wrong 3"])
    assert len(options) == 4
    assert options[correct_index] == "the right one"
    assert set(options) == {"the right one", "wrong 1", "wrong 2", "wrong 3"}


@patch("meetmind_ai.mcq_pipeline.settings")
@patch("meetmind_ai.mcq_pipeline.OpenAI")
def test_generate_quiz_modular_pipeline_end_to_end(mock_openai_cls, mock_settings):
    import json as json_mod

    from meetmind_ai import quiz_generation
    from meetmind_ai.schemas import ConceptSection

    mock_settings.require_openai.return_value = None
    mock_settings.openai_api_key = "test-key"
    mock_settings.llm_model = "gpt-4o"

    levels = ("remembering", "understanding", "applying")

    qa_batch_response = MagicMock()
    qa_batch_response.choices[0].message.content = json_mod.dumps({
        "items": [
            {"level": level, "question": "What did Raj commit to?",
             "correct_answer": "Testing diarization accuracy",
             "evidence_quote": "Raj said he is testing diarization accuracy"}
            for level in levels
        ]
    })
    distractor_batch_response = MagicMock()
    distractor_batch_response.choices[0].message.content = json_mod.dumps({
        "items": [
            {"level": level, "distractors": ["Writing the frontend", "Deploying to AWS", "Fixing a bug", "Reviewing a PR"]}
            for level in levels
        ]
    })
    mock_client = MagicMock()
    # One batched QA call, then one batched distractor call — not one pair per level.
    mock_client.chat.completions.create.side_effect = [qa_batch_response, distractor_batch_response]
    mock_openai_cls.return_value = mock_client

    sections = [ConceptSection(
        title="Standup", start=0.0, end=10.0,
        summary="Quick team status round.", key_concepts=["standup"],
    )]
    section_texts = {"Standup": "Raj said he is testing diarization accuracy today."}

    questions = quiz_generation.generate_quiz(sections, section_texts)

    assert mock_client.chat.completions.create.call_count == 2  # batched: 2 calls total, not 6
    assert len(questions) == 3
    for q in questions:
        assert q.question == "What did Raj commit to?"
        assert "Testing diarization accuracy" in q.options
        assert q.options[q.correct_index] == "Testing diarization accuracy"
        assert len(q.options) == 4
        assert q.bloom_level in ("remembering", "understanding", "applying")
