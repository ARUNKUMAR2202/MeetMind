"""
Optional REAL diarization backend using pyannote.audio's pretrained pipeline — this is
what actually approximates Zheng et al. (2022)'s tandem model / Du et al. (2022)'s SOND
overlap handling, as opposed to diarization.py's default pause-based heuristic.

Kept in its own module because pyannote + torch are heavy (~2GB+) and need a Hugging
Face token — not something the lightweight mock-mode demo should require.

Setup:
  1. pip install -r requirements-real-diarization.txt   (from ai-pipeline/)
  2. Accept the model terms at https://huggingface.co/pyannote/speaker-diarization-3.1
  3. Create a read token at https://huggingface.co/settings/tokens and set
     HUGGINGFACE_TOKEN in backend/.env
  4. Set USE_REAL_DIARIZATION=true in backend/.env

HONESTY NOTE: this has not been run against real audio anywhere in this codebase's
development — the environment that built it has no network access to the Hugging Face
Hub to download the pretrained weights. Treat this as a well-formed starting point that
needs to be validated on a real machine before you rely on its output, not as
production-verified code. This is intentionally the #1 item in TASK_SPLIT.md.
"""
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
