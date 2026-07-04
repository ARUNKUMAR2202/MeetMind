"""
Returns a realistic PipelineResult with zero network calls. This exists so:

  - The frontend teammate can build every dashboard screen today, without waiting on
    real OpenAI/Pinecone calls or spending API credits during UI iteration.
  - The backend teammate can test the full upload -> processing -> results flow,
    including the WebSocket status updates, deterministically.

Toggle with USE_MOCK_PIPELINE=true in .env (see backend/.env.example). Switch it off
once you're ready to test against real audio and your own API keys.
"""
from __future__ import annotations

import time

from .schemas import (
    ActionItem, ConceptSection, PipelineResult, ProfessionalOutput, QuizQuestion,
    RetrievedDocument, RoleSummary, SessionType, StudentOutput, Transcript,
    TranscriptSegment,
)


def _mock_transcript(session_id: str) -> Transcript:
    segments = [
        TranscriptSegment(start=0.0, end=4.2, text="Let's start the standup, quick round.",
                           speaker="Host", speaker_confidence=0.95),
        TranscriptSegment(start=4.5, end=11.0,
                           text="I finished the diarization integration yesterday, testing accuracy today.",
                           speaker="Rajamanickam", speaker_confidence=0.9),
        TranscriptSegment(start=11.3, end=18.0,
                           text="Great. Isabel, can you send the dashboard mockups by Friday?",
                           speaker="Host", speaker_confidence=0.95),
        TranscriptSegment(start=18.2, end=21.0, text="Yes, Friday works for me.",
                           speaker="Isabel", speaker_confidence=0.92),
        TranscriptSegment(start=21.5, end=30.0,
                           text="The RAG pipeline is retrieving documents in under two seconds now with the Pinecone index.",
                           speaker="Arunkumar", speaker_confidence=0.91),
    ]
    return Transcript(
        session_id=session_id,
        segments=segments,
        raw_text=" ".join(s.text for s in segments),
        noise_score=0.04,
    )


def generate_mock_result(session_id: str, session_type: SessionType) -> PipelineResult:
    transcript = _mock_transcript(session_id)
    student_output = None
    professional_output = None

    if session_type == SessionType.STUDENT:
        sections = [
            ConceptSection(
                title="Team status round",
                start=0.0, end=18.0,
                summary="The team ran a quick status round covering diarization testing progress and upcoming deliverables.",
                key_concepts=["standup format", "diarization accuracy testing", "deliverable deadlines"],
            ),
            ConceptSection(
                title="Retrieval performance",
                start=18.2, end=30.0,
                summary="The RAG pipeline now retrieves relevant documents in under two seconds using a Pinecone index.",
                key_concepts=["retrieval-augmented generation", "Pinecone", "sub-2-second latency"],
            ),
        ]
        quiz = [
            QuizQuestion(
                bloom_level="remembering",
                question="What is the retrieval latency the team reported for the RAG pipeline?",
                options=["Under 2 seconds", "Under 10 seconds", "About 1 minute", "Not measured yet"],
                correct_index=0,
                source_segment_start=21.5, source_segment_end=30.0,
                evidence_quote="Retrieval now happens in under two seconds using Pinecone.",
            ),
            QuizQuestion(
                bloom_level="understanding",
                question="Why does the team run a standup in a quick round format?",
                options=[
                    "To let each person give a short status update efficiently",
                    "To assign a single leader for the week",
                    "To review the full codebase line by line",
                    "To vote on the next sprint's deadline",
                ],
                correct_index=0,
                source_segment_start=0.0, source_segment_end=4.2,
                evidence_quote="The host asks to start the standup as a quick round.",
            ),
        ]
        student_output = StudentOutput(sections=sections, quiz=quiz, hallucination_flagged_count=0)
    else:
        action_items = [
            ActionItem(owner="Isabel", task="Send the dashboard mockups", due="Friday",
                       source_segment_start=11.3, source_segment_end=18.0, confidence=0.95),
            ActionItem(owner="Rajamanickam", task="Finish diarization accuracy testing", due=None,
                       source_segment_start=4.5, source_segment_end=11.0, confidence=0.85),
        ]
        role_summaries = [
            RoleSummary(role="Host", summary="Ran the standup; confirmed Isabel will send dashboard mockups Friday and Raj is validating diarization accuracy."),
            RoleSummary(role="Isabel", summary="You committed to sending the dashboard mockups by Friday."),
            RoleSummary(role="Rajamanickam", summary="You're finishing diarization integration testing."),
        ]
        professional_output = ProfessionalOutput(
            action_items=action_items, role_summaries=role_summaries, action_item_bertscore=63.5,
        )

    retrieved_documents = [
        RetrievedDocument(doc_id="doc-mock-1", title="RAG-Stack benchmark notes", score=0.88,
                          triggered_by_quote="The RAG pipeline is retrieving documents in under two seconds"),
    ]

    return PipelineResult(
        session_id=session_id,
        session_type=session_type,
        transcript=transcript,
        student_output=student_output,
        professional_output=professional_output,
        retrieved_documents=retrieved_documents,
        processing_seconds=1.2,
    )
