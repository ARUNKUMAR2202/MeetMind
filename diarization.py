from __future__ import annotations

from typing import Optional, Protocol

from .config import settings
from .schemas import Transcript, TranscriptSegment

# Gap between two segments (seconds) above which we assume a new speaker started —

_TURN_GAP_SECONDS = 0.6


class Diarizer(Protocol):
    def __call__(self, transcript: Transcript) -> Transcript: ...


def heuristic_diarize(transcript: Transcript, speaker_labels: list[str] | None = None) -> Transcript:
   
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
    if diarizer is not None:
        return diarizer(transcript)

    if settings.use_real_diarization and audio_file_path:
        from .real_diarization import real_diarize
        return real_diarize(transcript, audio_file_path)

    return heuristic_diarize(transcript)
