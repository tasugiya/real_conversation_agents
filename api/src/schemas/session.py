"""Session-related request/response models (docs/backend/02_BACKEND_PROCESS_DRAFT.md §4.3)."""

from datetime import datetime

from pydantic import BaseModel


class AuthRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_at: datetime


class CreateSessionRequest(BaseModel):
    topic_pack_id: str
    agent_count: int = 2
    language: str = "en"
    input_mode: str = "audio"  # "audio" | "text"
    output_mode: str = "audio_and_text"  # "audio_and_text" | "text_only"


class CreateSessionResponse(BaseModel):
    session_id: str
    status: str
    participants: list[str]


class SessionStatusResponse(BaseModel):
    session_id: str
    status: str
    expires_at: datetime | None = None
    review_available: bool = False


class StreamTicketResponse(BaseModel):
    stream_ticket: str
    expires_at: datetime


class GrammarFeedbackItem(BaseModel):
    utterance_id: str | None = None
    original: str
    suggestion: str
    explanation_ja: str
    severity: str = "medium"


class ReviewResponse(BaseModel):
    session_id: str
    summary: str
    score_total: int
    grammar_feedback: list[GrammarFeedbackItem] = []
