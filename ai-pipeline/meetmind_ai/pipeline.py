"""
The orchestrator. This is what backend/app/services/pipeline_service.py calls as a
background job after audio upload. Mirrors the thesis's Chapter 4 architecture:

  audio -> transcription -> diarization -> preprocessing -> [student | professional] branch -> RAG

Kept deliberately thin: each function it calls lives in its own module (single
responsibility, and each AI-pipeline sub-feature can be unit-tested/iterated on alone).
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from . import action_items as action_items_mod
from . import diarization as diarization_mod
from . import preprocessing as preprocessing_mod
from . import quiz_generation as quiz_mod
from . import summarization as summarization_mod
from . import transcription as transcription_mod
from .schemas import (
    PipelineResult, ProfessionalOutput, SessionType, StudentOutput, Transcript,
)

StageCallback = Callable[[str], None]


def _section_texts(transcript: Transcript, sections) -> dict[str, str]:
    texts = {}
    for section in sections:
        texts[section.title] = " ".join(
            s.text for s in transcript.segments if s.start >= section.start and s.end <= section.end
        ) or section.summary
    return texts


def run_pipeline(
    audio_file_path: str,
    session_id: str,
    session_type: SessionType,
    language: str = "en",
    on_stage: Optional[StageCallback] = None,
) -> PipelineResult:
    """
    `on_stage`, if given, is called with a short machine-readable stage name before
    each major step starts — e.g. "transcribing", "diarizing", "summarizing". Lets the
    caller (pipeline_service.py) push finer-grained progress over the session-status
    WebSocket instead of just "processing" for the whole duration. Never raises even
    if the callback itself throws — a broken progress notification shouldn't fail the
    actual pipeline run.
    """
    def emit(stage: str) -> None:
        if on_stage:
            try:
                on_stage(stage)
            except Exception:
                pass

    started = time.perf_counter()

    # Layer 2a
    emit("transcribing")
    transcript = transcription_mod.transcribe_audio(audio_file_path, session_id, language)

    # Layer 2b — real pyannote backend if USE_REAL_DIARIZATION is set (see
    # diarization.py's resolution order), otherwise the pause-based heuristic.
    # diarization_mod.needs_overlap_fallback() is available for whoever wires in
    # SOND-specific handling (see TASK_SPLIT.md) — not yet consumed here because the
    # real backend (pyannote) already handles overlap reasonably on its own.
    emit("diarizing")
    transcript = diarization_mod.diarize(transcript, audio_file_path=audio_file_path)

    # Layer 3 — only actually reconstructs if noise_score crosses the threshold
    if transcript.noise_score >= preprocessing_mod.settings.noise_threshold:
        emit("cleaning_transcript")
    transcript = preprocessing_mod.reconstruct_if_needed(transcript)

    student_output = None
    professional_output = None

    if session_type == SessionType.STUDENT:
        emit("summarizing")
        sections = summarization_mod.segment_by_topic(transcript)
        section_texts = _section_texts(transcript, sections)

        emit("generating_quiz")
        quiz = quiz_mod.generate_quiz(sections, section_texts)
        sections_by_span = {(s.start, s.end): section_texts.get(s.title, "") for s in sections}
        flagged = quiz_mod.flag_hallucinations(quiz, section_texts, sections_by_span)
        student_output = StudentOutput(
            sections=sections, quiz=quiz, hallucination_flagged_count=flagged,
        )
    else:
        emit("extracting_action_items")
        action_items = action_items_mod.extract_action_items(transcript)

        emit("summarizing")
        role_summaries = summarization_mod.aspect_based_role_summaries(transcript)
        bertscore = action_items_mod.score_action_items(action_items)
        professional_output = ProfessionalOutput(
            action_items=action_items, role_summaries=role_summaries,
            action_item_bertscore=bertscore,
        )

    emit("finalizing")
    return PipelineResult(
        session_id=session_id,
        session_type=session_type,
        transcript=transcript,
        student_output=student_output,
        professional_output=professional_output,
        processing_seconds=round(time.perf_counter() - started, 2),
    )
