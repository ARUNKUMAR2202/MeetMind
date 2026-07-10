
from __future__ import annotations

from .config import settings
from .schemas import Transcript

_pipeline_cache = None


def _get_pipeline():
    global _pipeline_cache
    if _pipeline_cache is not None:
        return _pipeline_cache

    try:
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise RuntimeError(
            "pyannote.audio isn't installed. Run "
            "`pip install -r requirements-real-diarization.txt` from ai-pipeline/ first."
        ) from exc

    if not settings.huggingface_token:
        raise RuntimeError(
            "HUGGINGFACE_TOKEN is not set. Real diarization needs a Hugging Face read "
            "token with access to pyannote/speaker-diarization-3.1 — see this module's "
            "docstring for setup steps."
        )

    _pipeline_cache = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1", use_auth_token=settings.huggingface_token,
    )
    return _pipeline_cache


def real_diarize(transcript: Transcript, audio_file_path: str) -> Transcript:
    """
    Runs pyannote on the actual audio file to get real speaker turns, then assigns each
    Whisper segment the speaker whose turn overlaps it the most. Unlike the heuristic,
    this needs the original audio (Whisper's timestamps alone aren't enough).
    """
    pipeline = _get_pipeline()
    diarization = pipeline(audio_file_path)

    turns = [
        (turn.start, turn.end, label)
        for turn, _, label in diarization.itertracks(yield_label=True)
    ]

    def _speaker_for(seg_start: float, seg_end: float) -> str | None:
        best_label, best_overlap = None, 0.0
        for t_start, t_end, label in turns:
            overlap = max(0.0, min(seg_end, t_end) - max(seg_start, t_start))
            if overlap > best_overlap:
                best_overlap, best_label = overlap, label
        return best_label

    new_segments = [
        seg.model_copy(update={
            "speaker": _speaker_for(seg.start, seg.end) or seg.speaker,
            "speaker_confidence": 0.9,
        })
        for seg in transcript.segments
    ]
    return transcript.model_copy(update={"segments": new_segments})
