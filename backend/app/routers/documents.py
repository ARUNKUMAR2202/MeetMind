from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..models import MeetingSession, ReferenceDocument, User
from ..schemas import DocumentOut

router = APIRouter(prefix="/sessions/{session_id}/documents", tags=["documents"])

_CHUNK_SIZE_CHARS = 1500


class DocumentIn(BaseModel):
    title: str
    text: str  # extracted text; frontend/pdf-parsing happens before this call


def _chunk(text: str, size: int = _CHUNK_SIZE_CHARS) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)] or [text]


@router.post("", response_model=DocumentOut, status_code=201)
def upload_document(
    session_id: str,
    payload: DocumentIn,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = db.get(MeetingSession, session_id)
    if session is None or session.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.session_type != "professional":
        raise HTTPException(
            status_code=400,
            detail="Document retrieval (RAG) is a professional-team feature — "
                   "student sessions get summaries and quizzes instead.",
        )

    chunks = _chunk(payload.text)

    if not settings.use_mock_pipeline:
        from meetmind_ai.rag import index_document
        chunk_count = index_document(session_id, payload.title, chunks)
    else:
        chunk_count = len(chunks)  # mock mode: skip the real Pinecone call

    doc = ReferenceDocument(session_id=session_id, title=payload.title, chunk_count=chunk_count)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return DocumentOut.model_validate(doc)


@router.get("", response_model=list[DocumentOut])
def list_documents(
    session_id: str, db: DBSession = Depends(get_db), current_user: User = Depends(get_current_user),
):
    session = db.get(MeetingSession, session_id)
    if session is None or session.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found.")
    return [DocumentOut.model_validate(d) for d in session.documents]
