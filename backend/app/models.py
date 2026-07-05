import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    full_name: Mapped[str] = mapped_column(String)
    # "student" or "professional" — drives which dashboard they land on by default.
    account_type: Mapped[str] = mapped_column(String, default="student")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    sessions: Mapped[list["MeetingSession"]] = relationship(back_populates="owner")


class MeetingSession(Base):
    """One uploaded lecture or meeting recording and everything the pipeline produced for it."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String)
    session_type: Mapped[str] = mapped_column(String)  # "student" | "professional"

    # uploaded -> processing -> completed | failed
    status: Mapped[str] = mapped_column(String, default="uploaded")
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    audio_path: Mapped[str] = mapped_column(String)
    processing_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Pipeline outputs, stored as JSON. See ai_pipeline.schemas for the exact shape —
    # these columns are the serialized form of PipelineResult's sub-objects.
    transcript_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    student_output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    professional_output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    retrieved_documents_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    owner: Mapped["User"] = relationship(back_populates="sessions")
    documents: Mapped[list["ReferenceDocument"]] = relationship(
        back_populates="session", cascade="all, delete-orphan",
    )


class Room(Base):
    """A live video-conference meeting (Phase 1). Decoupled from MeetingSession —
    a room is just "people on a call"; Phase 3 links a recording session to the
    room it was captured in. host_id/participant.user_id are free-form guest ids
    for now (see services/room_manager.py's WS handshake) — Phase 2 swaps these
    for real auth.users ids and adds RLS once Supabase Auth is wired in."""

    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String, unique=True, index=True)
    host_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="live")  # scheduled | live | ended
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    participants: Mapped[list["Participant"]] = relationship(
        back_populates="room", cascade="all, delete-orphan",
    )


class Participant(Base):
    """One join for one person in one room. A person who leaves and rejoins gets a
    second row — this is a log of visits, not a membership roster."""

    __tablename__ = "participants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"))
    user_id: Mapped[str] = mapped_column(String)
    display_name: Mapped[str] = mapped_column(String)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    left_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    room: Mapped["Room"] = relationship(back_populates="participants")


class ReferenceDocument(Base):
    """A document uploaded for RAG retrieval (Layer 6) — slides, briefs, etc."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    title: Mapped[str] = mapped_column(String)
    chunk_count: Mapped[int] = mapped_column(default=0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    session: Mapped["MeetingSession"] = relationship(back_populates="documents")
