"""
meetmind_ai — the AI pipeline package for MeetMind AI.

Owned by: AI Pipeline teammate (ASR / diarization / summarization / quiz / RAG).

This package is deliberately independent of the web framework (FastAPI) so it can be
developed, unit-tested, and iterated on without running the whole backend. The backend
imports `run_pipeline` (see pipeline.py) and calls it as a background job.
"""

from .mock import generate_mock_result
from .pipeline import run_pipeline, PipelineResult

__all__ = ["run_pipeline", "PipelineResult", "generate_mock_result"]
