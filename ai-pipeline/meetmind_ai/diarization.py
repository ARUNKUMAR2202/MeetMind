
from __future__ import annotations

from typing import Optional, Protocol

from .config import settings
from .schemas import Transcript, TranscriptSegment

# Gap between two segments (seconds) above which we assume a new speaker started —
# a crude proxy until real diarization is wired in.
_TURN_GAP_SECONDS = 0.6


class Diarizer(Protocol):
    def __call__(self, transcript: Transcript) -> Transcript: ...


def heuristic_diarize(transcript: Transcript, speaker_labels: list[str] | None = None) -> Transcript:
    """
    Assigns alternating speaker labels whenever the pause between two Whisper segments
    exceeds _TURN_GAP_SECONDS. This is a placeholder, not a diarization model — it will
    misattribute fast back-and-forth exchanges and can't handle real overlap (that's
    exactly the gap SOND is meant to close).
    """
    labels = speaker_labels or [f"Speaker {i+1}" for i in range(6)]
    new_segments: list[TranscriptSegment] = []
    current_speaker_idx = 0
    prev_end = None

    for seg in transcript.segments:
        if prev_end is not None and (seg.start - prev_end) > _TURN_GAP_SECONDS:
            current_speaker_idx = (current_speaker_idx + 1) % len(labels)
        new_segments.append(
            seg.model_copy(update={
                "speaker": labels[current_speaker_idx],
                "speaker_confidence": 0.5,  # deliberately low — this is a heuristic, not a model
            })
        )
        prev_end = seg.end

    return transcript.model_copy(update={"segments": new_segments})


def needs_overlap_fallback(transcript: Transcript, overlap_ratio_threshold: float = 0.2) -> bool:
    """
    Decides whether to route through the SOND-style overlap-aware path (Du et al., 2022)
    instead of the standard tandem path (Zheng et al., 2022). Estimated from how often
    segments' timestamps overlap — a real implementation would use the ASR model's
    frame-level confidence instead.
    """
    segs = sorted(transcript.segments, key=lambda s: s.start)
    if len(segs) < 2:
        return False
    overlaps = sum(1 for a, b in zip(segs, segs[1:]) if b.start < a.end)
    return (overlaps / len(segs)) > overlap_ratio_threshold


def diarize(
    transcript: Transcript,
    audio_file_path: Optional[str] = None,
    diarizer: Optional[Diarizer] = None,
) -> Transcript:
    """
    Entry point the pipeline calls. Resolution order:
      1. An explicitly passed `diarizer` always wins (used by tests, or to force a
         specific backend).
      2. If USE_REAL_DIARIZATION is set AND an audio file path is available, routes to
         the pyannote-based real diarizer (see real_diarization.py).
      3. Otherwise falls back to the pause-based heuristic above.

    If the real backend is requested but fails to load (missing dependency, missing
    HF token, bad audio path), this re-raises rather than silently falling back to the
    heuristic — silently degrading diarization quality without telling anyone would be
    worse than a loud failure during setup.
    """
    if diarizer is not None:
        return diarizer(transcript)

    if settings.use_real_diarization and audio_file_path:
        from .real_diarization import real_diarize
        return real_diarize(transcript, audio_file_path)

    return heuristic_diarize(transcript)
