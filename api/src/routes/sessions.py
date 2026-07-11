"""POST /v1/sessions, stream-ticket, end, and review retrieval
(docs/backend/02_BACKEND_PROCESS_DRAFT.md §4.3).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from ..middleware.app_check import require_app_check
from ..middleware.auth import issue_stream_ticket, require_access_token
from ..middleware.rate_limit import enforce_rate_limit
from ..schemas.session import (
    CreateSessionRequest,
    CreateSessionResponse,
    GrammarFeedbackItem,
    ReviewResponse,
    SessionStatusResponse,
    StreamTicketResponse,
)
from ..services import firestore_client
from ..services.agent_engine_client import create_agent_session
from ..services.gemini_client import generate_review

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])

SESSIONS_COLLECTION = "sessions"
SESSION_MESSAGES_COLLECTION = "session_messages"
REVIEWS_COLLECTION = "reviews"


@router.post(
    "",
    response_model=CreateSessionResponse,
    dependencies=[
        Depends(enforce_rate_limit),
        Depends(require_access_token),
        Depends(require_app_check),
    ],
)
async def create_session(body: CreateSessionRequest) -> CreateSessionResponse:
    session_id = uuid.uuid4().hex
    agent_session_id = await create_agent_session(user_id=session_id)
    participants = ["alice", "bob"][: max(body.agent_count, 1)]

    firestore_client.create_document(
        SESSIONS_COLLECTION,
        session_id,
        {
            "session_id": session_id,
            "status": "created",
            "topic_pack_id": body.topic_pack_id,
            "agent_count": body.agent_count,
            "agent_session_id": agent_session_id,
            "participants": participants,
            "started_at": datetime.now(timezone.utc),
        },
    )
    return CreateSessionResponse(session_id=session_id, status="created", participants=participants)


@router.get(
    "/{session_id}",
    response_model=SessionStatusResponse,
    dependencies=[Depends(require_access_token)],
)
async def get_session(session_id: str) -> SessionStatusResponse:
    doc = firestore_client.get_document(SESSIONS_COLLECTION, session_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    review = firestore_client.get_document(REVIEWS_COLLECTION, session_id)
    return SessionStatusResponse(
        session_id=session_id,
        status=doc.get("status", "unknown"),
        expires_at=doc.get("expires_at"),
        review_available=review is not None,
    )


@router.post(
    "/{session_id}/stream-ticket",
    response_model=StreamTicketResponse,
    dependencies=[Depends(enforce_rate_limit), Depends(require_access_token)],
)
async def create_stream_ticket(session_id: str) -> StreamTicketResponse:
    doc = firestore_client.get_document(SESSIONS_COLLECTION, session_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    ticket, expires_at = issue_stream_ticket(session_id)
    return StreamTicketResponse(stream_ticket=ticket, expires_at=expires_at)


@router.post(
    "/{session_id}/end",
    response_model=ReviewResponse,
    dependencies=[Depends(enforce_rate_limit), Depends(require_access_token)],
)
async def end_session(session_id: str) -> ReviewResponse:
    doc = firestore_client.get_document(SESSIONS_COLLECTION, session_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")

    firestore_client.update_document(SESSIONS_COLLECTION, session_id, {"status": "ending"})

    transcript = _load_transcript(session_id)
    result = generate_review(transcript)
    grammar_feedback = [
        GrammarFeedbackItem(**item.model_dump()) for item in result.grammar_feedback
    ]

    firestore_client.create_document(
        REVIEWS_COLLECTION,
        session_id,
        {
            "session_id": session_id,
            "summary": result.summary,
            "score_total": result.score_total,
            "grammar_feedback": [item.model_dump() for item in grammar_feedback],
        },
    )
    firestore_client.update_document(SESSIONS_COLLECTION, session_id, {"status": "completed"})

    return ReviewResponse(
        session_id=session_id,
        summary=result.summary,
        score_total=result.score_total,
        grammar_feedback=grammar_feedback,
    )


@router.get(
    "/{session_id}/review",
    response_model=ReviewResponse,
    dependencies=[Depends(require_access_token)],
)
async def get_review(session_id: str) -> ReviewResponse:
    doc = firestore_client.get_document(REVIEWS_COLLECTION, session_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review not found")
    return ReviewResponse(**doc)


def _load_transcript(session_id: str) -> list[dict]:
    docs = (
        firestore_client.get_client()
        .collection(SESSION_MESSAGES_COLLECTION)
        .where("session_id", "==", session_id)
        .order_by("created_at")
        .stream()
    )
    return [d.to_dict() for d in docs]
