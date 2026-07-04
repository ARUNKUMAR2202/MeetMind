"""
Tests the ROUTING logic in diarization.py (which backend gets picked) and confirms
the optional real backends fail loudly and clearly when their heavy dependencies
aren't installed — which they genuinely aren't in this test environment, so these are
real (not mocked) checks of the error path every dev will hit before running
`pip install -r requirements-real-*.txt`.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from meetmind_ai.diarization import diarize, heuristic_diarize
from meetmind_ai.schemas import ActionItem, Transcript, TranscriptSegment


def _sample_transcript() -> Transcript:
    return Transcript(
        session_id="routing-test",
        segments=[TranscriptSegment(start=0.0, end=2.0, text="hello")],
        raw_text="hello",
    )


def test_diarize_defaults_to_heuristic_when_flag_off():
    with patch("meetmind_ai.diarization.settings") as mock_settings:
        mock_settings.use_real_diarization = False
        result = diarize(_sample_transcript())
        assert result.segments[0].speaker_confidence == 0.5  # heuristic's tell-tale low confidence


def test_diarize_falls_back_to_heuristic_without_audio_path_even_if_flag_on():
    with patch("meetmind_ai.diarization.settings") as mock_settings:
        mock_settings.use_real_diarization = True
        result = diarize(_sample_transcript(), audio_file_path=None)
        assert result.segments[0].speaker_confidence == 0.5


def test_diarize_explicit_override_wins_regardless_of_settings():
    calls = []

    def fake_diarizer(transcript):
        calls.append(transcript.session_id)
        return transcript

    with patch("meetmind_ai.diarization.settings") as mock_settings:
        mock_settings.use_real_diarization = True
        diarize(_sample_transcript(), audio_file_path="fake.wav", diarizer=fake_diarizer)
    assert calls == ["routing-test"]


def test_diarize_routes_to_real_backend_when_flag_on_and_audio_path_given():
    with patch("meetmind_ai.diarization.settings") as mock_settings, \
         patch("meetmind_ai.real_diarization.real_diarize") as mock_real:
        mock_settings.use_real_diarization = True
        mock_real.return_value = _sample_transcript()
        diarize(_sample_transcript(), audio_file_path="fake.wav")
        mock_real.assert_called_once()


def test_real_diarize_fails_clearly_without_pyannote_installed():
    from meetmind_ai.real_diarization import real_diarize
    with pytest.raises(RuntimeError, match="pyannote.audio isn't installed"):
        real_diarize(_sample_transcript(), "fake.wav")


def test_real_bertscore_fails_clearly_without_bert_score_installed():
    from meetmind_ai.real_bertscore import real_bertscore
    items = [ActionItem(owner="A", task="do the thing", source_segment_start=0, source_segment_end=1)]
    with pytest.raises(RuntimeError, match="bert-score isn't installed"):
        real_bertscore(items, "reference summary text")


def test_real_bertscore_returns_zero_for_empty_candidates_without_needing_the_dependency():
    from meetmind_ai.real_bertscore import real_bertscore
    assert real_bertscore([], "reference text") == 0.0
