"""
Layer 2a — Transcription (Radford et al., 2022, "Robust Speech Recognition via
Large-Scale Weak Supervision" — Whisper).

Whisper alone gives us accurate text with timestamps but NO speaker labels. Speaker
attribution happens in diarization.py (Zheng et al., 2022 / Du et al., 2022).
"""
from __future__ import annotations

import re

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import settings
from .schemas import Transcript, TranscriptSegment

_FILLER_WORDS = {
    "um", "uh", "erm", "hmm", "like", "you know", "sort of", "kind of", "i mean",
}


def _client() -> OpenAI:
    settings.require_openai()
    return OpenAI(api_key=settings.openai_api_key)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
def transcribe_audio(audio_file_path: str, session_id: str, language: str = "en") -> Transcript:
    """
    Calls OpenAI's Whisper API (whisper-1) with verbose_json to get word/segment-level
    timestamps. Requires OPENAI_API_KEY to be set.
    """
    client = _client()
    with open(audio_file_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model=settings.whisper_model,
            file=f,
            language=language,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    segments = [
        TranscriptSegment(start=seg.start, end=seg.end, text=seg.text.strip())
        for seg in response.segments
    ]
    raw_text = " ".join(s.text for s in segments)

    return Transcript(
        session_id=session_id,
        language=language,
        segments=segments,
        raw_text=raw_text,
        noise_score=estimate_noise_score(raw_text),
    )


def estimate_noise_score(raw_text: str) -> float:
    """
    Cheap disfluency-ratio heuristic that decides whether Tan et al. (2023)'s
    Reconstruct-Before-Summarize preprocessing step should run (see preprocessing.py).
    This is NOT a research contribution on its own — it's a practical trigger.
    """
    words = re.findall(r"[a-zA-Z']+", raw_text.lower())
    if not words:
        return 0.0
    filler_count = sum(1 for w in words if w in _FILLER_WORDS)
    # Repetition: consecutive duplicate words ("the the report")
    repeats = sum(1 for a, b in zip(words, words[1:]) if a == b)
    return round(min(1.0, (filler_count + repeats) / len(words) * 4), 3)
