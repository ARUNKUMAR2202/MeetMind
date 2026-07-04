"""
Bridges the web layer to the ai-pipeline package. Runs as a FastAPI BackgroundTask —
good enough for a demo/thesis submission; for real production load with many
concurrent sessions, swap this for a proper task queue (Celery/RQ) without changing
`run_pipeline_job`'s signature, since routers only ever call it via
`background_tasks.add_task(run_pipeline_job, ...)`.
"""
from datetime import datetime, timezone

from meetmind_ai import generate_mock_result, run_pipeline
from meetmind_ai.schemas import SessionType

from ..config import settings
from ..database import SessionLocal
from ..models import MeetingSession
from .storage_service import get_local_path
from .ws_manager import broadcast_sync


def run_pipeline_job(session_id: str) -> None:
    db = SessionLocal()
    try:
        session = db.get(MeetingSession, session_id)
        if session is None:
            return

        session.status = "processing"
        db.commit()
        broadcast_sync(session_id, {"status": "processing"})

        try:
            session_type = SessionType(session.session_type)
            if settings.use_mock_pipeline:
                result = generate_mock_result(session_id, session_type)
            else:
                local_path = get_local_path(session.audio_path)
                on_stage = lambda stage: broadcast_sync(session_id, {"status": "processing", "stage": stage})
                result = run_pipeline(local_path, session_id, session_type, on_stage=on_stage)

            session.status = "completed"
            session.completed_at = datetime.now(timezone.utc)
            session.processing_seconds = result.processing_seconds
            session.transcript_json = result.transcript.model_dump()
            session.student_output_json = (
                result.student_output.model_dump() if result.student_output else None
            )
            session.professional_output_json = (
                result.professional_output.model_dump() if result.professional_output else None
            )
            session.retrieved_documents_json = [d.model_dump() for d in result.retrieved_documents]
            db.commit()
            broadcast_sync(session_id, {"status": "completed"})

        except Exception as exc:  # noqa: BLE001 — surface any pipeline failure to the client
            session.status = "failed"
            session.error_message = str(exc)
            db.commit()
            broadcast_sync(session_id, {"status": "failed", "error": str(exc)})

    finally:
        db.close()
