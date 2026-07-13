"""POST /v1/sessions, stream-ticket, end, review retrieval, and review retry
(docs/backend/02_BACKEND_PROCESS_DRAFT.md §4.3).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from ..config import get_settings
from ..middleware.app_check import require_app_check
from ..middleware.auth import issue_stream_ticket, require_access_token
from ..middleware.rate_limit import rate_limiter
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
from ..services.memory_monitor import memory_usage_ratio
from ..services.personas import select_personas

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])
logger = logging.getLogger("sessions")

SESSIONS_COLLECTION = "sessions"
SESSION_MESSAGES_COLLECTION = "session_messages"
REVIEWS_COLLECTION = "reviews"

# Extra buffer added on top of session_max_duration_seconds before a
# created/ending session is considered stale (network delays, review
# generation taking a moment, etc.).
_STALE_GRACE_SECONDS = 120


@router.post(
    "",
    response_model=CreateSessionResponse,
    dependencies=[
        Depends(rate_limiter("session_setup")),
        Depends(require_access_token),
        Depends(require_app_check),
    ],
)
async def create_session(body: CreateSessionRequest) -> CreateSessionResponse:
    # Enforce concurrent session limit (P1)
    settings = get_settings()
    raw = list(
        firestore_client.get_client()
        .collection(SESSIONS_COLLECTION)
        .where("status", "in", ["created", "ending"])
        .stream()
    )
    active, stale = _filter_stale_sessions(raw)
    _mark_stale_sessions_abandoned(stale)
    if len(active) >= settings.max_concurrent_sessions:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="server is at capacity, please try again later",
        )

    # Proactively reject before an OOM-kill takes the instance down mid-
    # conversation instead (BUG-023, see 2026-07-12 incident in LOG.md).
    # Same response as the capacity check above -- the client doesn't need
    # to distinguish why, both mean "try again shortly".
    usage_ratio = memory_usage_ratio()
    if usage_ratio is not None and usage_ratio >= settings.memory_pressure_threshold:
        logger.warning(
            "create_session: memory usage %.0f%% >= threshold %.0f%%, rejecting",
            usage_ratio * 100, settings.memory_pressure_threshold * 100,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="server is at capacity, please try again later",
        )

    session_id = uuid.uuid4().hex
    agent_session_id = await create_agent_session(user_id=session_id)

    selected = select_personas(body.agent_count)
    participant_names = [p.name for p in selected]
    participant_personalities = {p.name: p.personality for p in selected}

    firestore_client.create_document(
        SESSIONS_COLLECTION,
        session_id,
        {
            "session_id": session_id,
            "status": "created",
            "topic_pack_id": body.topic_pack_id,
            "agent_count": body.agent_count,
            "agent_session_id": agent_session_id,
            "participants": participant_names,
            "participant_personalities": participant_personalities,
            "language": body.language,
            "started_at": datetime.now(timezone.utc),
        },
    )
    return CreateSessionResponse(
        session_id=session_id,
        status="created",
        participants=participant_names,
    )


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
    dependencies=[Depends(rate_limiter("stream_ticket")), Depends(require_access_token)],
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
    dependencies=[Depends(rate_limiter("review")), Depends(require_access_token)],
)
async def end_session(session_id: str) -> ReviewResponse:
    doc = firestore_client.get_document(SESSIONS_COLLECTION, session_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")

    # Idempotency: return existing review if already completed (BUG-006 fix)
    if doc.get("status") == "completed":
        existing_review = firestore_client.get_document(REVIEWS_COLLECTION, session_id)
        if existing_review is not None:
            return ReviewResponse(**existing_review)

    firestore_client.update_document(SESSIONS_COLLECTION, session_id, {"status": "ending"})

    transcript = _load_transcript(session_id)
    result = generate_review(transcript)
    grammar_feedback = [
        GrammarFeedbackItem(**item.model_dump()) for item in result.grammar_feedback
    ]

    now = datetime.now(timezone.utc)
    metrics = _compute_session_metrics(transcript, doc.get("started_at"), now)

    firestore_client.create_document(
        REVIEWS_COLLECTION,
        session_id,
        {
            "session_id": session_id,
            "summary": result.summary,
            "score_total": result.score_total,
            "score_communication": result.score_communication,
            "score_language": result.score_language,
            "conversation_feedback": result.conversation_feedback,
            "grammar_feedback": [item.model_dump() for item in grammar_feedback],
            **metrics,
        },
    )
    # BUG-013 fix: expires_at = ended_at + 24h (not creation time + 24h)
    firestore_client.update_document(
        SESSIONS_COLLECTION,
        session_id,
        {
            "status": "completed",
            "ended_at": now,
            "expires_at": now + timedelta(hours=24),
        },
    )

    return ReviewResponse(
        session_id=session_id,
        summary=result.summary,
        score_total=result.score_total,
        score_communication=result.score_communication,
        score_language=result.score_language,
        conversation_feedback=result.conversation_feedback,
        grammar_feedback=grammar_feedback,
        **metrics,
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


@router.post(
    "/{session_id}/review/retry",
    response_model=ReviewResponse,
    dependencies=[Depends(rate_limiter("review")), Depends(require_access_token)],
)
async def retry_review(session_id: str) -> ReviewResponse:
    """Re-generate a review for a completed session. Limited to 3 retries."""
    doc = firestore_client.get_document(SESSIONS_COLLECTION, session_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    if doc.get("status") != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session must be completed before retrying review",
        )

    existing_review = firestore_client.get_document(REVIEWS_COLLECTION, session_id)
    retry_count: int = (existing_review or {}).get("retry_count", 0)
    if retry_count >= 3:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="retry limit reached (max 3)",
        )

    transcript = _load_transcript(session_id)
    result = generate_review(transcript)
    grammar_feedback = [
        GrammarFeedbackItem(**item.model_dump()) for item in result.grammar_feedback
    ]

    updated = {
        "summary": result.summary,
        "score_total": result.score_total,
        "score_communication": result.score_communication,
        "score_language": result.score_language,
        "conversation_feedback": result.conversation_feedback,
        "grammar_feedback": [item.model_dump() for item in grammar_feedback],
        "retry_count": retry_count + 1,
    }
    if existing_review is None:
        firestore_client.create_document(
            REVIEWS_COLLECTION, session_id, {"session_id": session_id, **updated}
        )
    else:
        firestore_client.update_document(REVIEWS_COLLECTION, session_id, updated)

    return ReviewResponse(
        session_id=session_id,
        summary=result.summary,
        score_total=result.score_total,
        score_communication=result.score_communication,
        score_language=result.score_language,
        conversation_feedback=result.conversation_feedback,
        grammar_feedback=grammar_feedback,
    )


def _filter_stale_sessions(docs: list) -> tuple[list, list]:
    """Split created/ending session docs into (still-active, stale) by age.

    A session whose started_at is older than session_max_duration_seconds +
    _STALE_GRACE_SECONDS is treated as abandoned (the client disconnected or
    crashed without ever calling POST .../end) rather than counted against
    max_concurrent_sessions. Docs with no started_at are kept active (fail
    safe -- never staleness-evict something we can't age-check).
    """
    settings = get_settings()
    threshold = timedelta(seconds=settings.session_max_duration_seconds + _STALE_GRACE_SECONDS)
    now = datetime.now(timezone.utc)
    active, stale = [], []
    for d in docs:
        started_at = d.to_dict().get("started_at")
        (stale if started_at and (now - started_at) > threshold else active).append(d)
    return active, stale


def _mark_stale_sessions_abandoned(stale_docs: list) -> None:
    """Best-effort: free up stale sessions' concurrency slot for good so future
    create_session calls don't need to re-filter them every time. Never raises
    -- a failure here must not block the session creation that triggered it.
    """
    now = datetime.now(timezone.utc)
    for d in stale_docs:
        try:
            firestore_client.update_document(
                SESSIONS_COLLECTION, d.id, {"status": "abandoned", "ended_at": now}
            )
        except Exception:  # noqa: BLE001
            pass


def _load_transcript(session_id: str) -> list[dict]:
    docs = (
        firestore_client.get_client()
        .collection(SESSION_MESSAGES_COLLECTION)
        .where("session_id", "==", session_id)
        .order_by("created_at")
        .stream()
    )
    return [d.to_dict() for d in docs]


def _compute_session_metrics(
    transcript: list[dict],
    started_at: datetime | None,
    ended_at: datetime | None,
) -> dict:
    """Compute objective session metrics from the transcript (Scoring Observer)."""
    user_msgs = [m for m in transcript if m.get("role") == "user"]
    ai_msgs = [m for m in transcript if m.get("role") == "assistant"]
    question_count = sum(
        1 for m in user_msgs if "?" in m.get("transcript", "")
    )
    duration_seconds: int | None = None
    if started_at and ended_at:
        try:
            delta = ended_at - started_at
            duration_seconds = int(delta.total_seconds())
        except Exception:
            pass
    return {
        "user_utterance_count": len(user_msgs),
        "ai_utterance_count": len(ai_msgs),
        "question_count": question_count,
        "duration_seconds": duration_seconds,
    }
