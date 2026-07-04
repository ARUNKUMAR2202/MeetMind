"""
Shared data contracts between pipeline stages. Keeping these in one file means the
backend, the pipeline, and unit tests all agree on shape without importing each other's
internals.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SessionType(str, Enum):
    STUDENT = "student"
    PROFESSIONAL = "professional"


class TranscriptSegment(BaseModel):
    """One utterance, after Whisper (Radford et al., 2022) + diarization (Zheng et al., 2022)."""

    start: float  # seconds
    end: float  # seconds
    text: str
    speaker: Optional[str] = None  # None until diarization runs
    speaker_confidence: Optional[float] = None


class Transcript(BaseModel):
    session_id: str
    language: str = "en"
    segments: list[TranscriptSegment]
    raw_text: str
    noise_score: float = 0.0  # estimated disfluency ratio, drives Tan et al. RPB step
    was_reconstructed: bool = False  # True if RPB preprocessing ran


class ConceptSection(BaseModel):
    """One topic block from Liu et al. (2021) dynamic sliding window segmentation."""

    title: str
    start: float
    end: float
    summary: str
    key_concepts: list[str] = Field(default_factory=list)


class QuizQuestion(BaseModel):
    bloom_level: str  # remembering | understanding | applying
    question: str
    options: list[str]
    correct_index: int
    source_segment_start: float  # timestamp this question is grounded in
    source_segment_end: float
    evidence_quote: str = ""  # short paraphrase-safe pointer used for hallucination checks


class ActionItem(BaseModel):
    owner: str  # speaker name/label the task is assigned to
    task: str
    due: Optional[str] = None
    source_segment_start: float
    source_segment_end: float
    confidence: float = 1.0


class RoleSummary(BaseModel):
    role: str  # e.g. "host", or a participant's speaker label
    summary: str


class RetrievedDocument(BaseModel):
    doc_id: str
    title: str
    score: float
    triggered_by_quote: str


class StudentOutput(BaseModel):
    sections: list[ConceptSection]
    quiz: list[QuizQuestion]
    hallucination_flagged_count: int = 0


class ProfessionalOutput(BaseModel):
    action_items: list[ActionItem]
    role_summaries: list[RoleSummary]
    action_item_bertscore: Optional[float] = None


class PipelineResult(BaseModel):
    session_id: str
    session_type: SessionType
    transcript: Transcript
    student_output: Optional[StudentOutput] = None
    professional_output: Optional[ProfessionalOutput] = None
    retrieved_documents: list[RetrievedDocument] = Field(default_factory=list)
    processing_seconds: float = 0.0
