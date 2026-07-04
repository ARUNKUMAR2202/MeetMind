from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    account_type: Literal["student", "professional"] = "student"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    account_type: str

    model_config = ConfigDict(from_attributes=True)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class SessionOut(BaseModel):
    id: str
    title: str
    session_type: str
    status: str
    error_message: str | None = None
    processing_seconds: float | None = None
    transcript: dict[str, Any] | None = None
    student_output: dict[str, Any] | None = None
    professional_output: dict[str, Any] | None = None
    retrieved_documents: list[Any] | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, session) -> "SessionOut":
        return cls(
            id=session.id,
            title=session.title,
            session_type=session.session_type,
            status=session.status,
            error_message=session.error_message,
            processing_seconds=session.processing_seconds,
            transcript=session.transcript_json,
            student_output=session.student_output_json,
            professional_output=session.professional_output_json,
            retrieved_documents=session.retrieved_documents_json,
            created_at=session.created_at,
            completed_at=session.completed_at,
        )


class SessionListItem(BaseModel):
    id: str
    title: str
    session_type: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentOut(BaseModel):
    id: str
    title: str
    chunk_count: int

    model_config = ConfigDict(from_attributes=True)
