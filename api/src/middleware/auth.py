"""password -> short-lived token, and one-time WebSocket stream tickets
(docs/infra/03_SECURITY.md §2).
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import get_settings
from ..services import firestore_client
from ..services.secret_manager_client import get_secret

_bearer_scheme = HTTPBearer(auto_error=False)

STREAM_TICKETS_COLLECTION = "stream_tickets"


def _secret_id(name: str) -> str:
    """Secret names are suffixed per environment (-dev / -prod) since dev and
    prod share a single GCP project; unsuffixed names would collide
    (docs/infra/02_PARAMS_DEF.md §4)."""
    return f"{name}-{get_settings().environment}"


def verify_password(username: str, password: str) -> bool:
    expected_username = get_secret(_secret_id("shared-auth-username"))
    password_hash = get_secret(_secret_id("shared-auth-password-hash"))
    if not secrets.compare_digest(username, expected_username):
        return False
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def issue_access_token() -> tuple[str, datetime]:
    settings = get_settings()
    signing_secret = get_secret(_secret_id("token-signing-secret"))
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=settings.auth_token_ttl_seconds
    )
    token = jwt.encode(
        {"exp": expires_at, "scope": "session-api"},
        signing_secret,
        algorithm="HS256",
    )
    return token, expires_at


def _decode_token(token: str) -> dict:
    signing_secret = get_secret(_secret_id("token-signing-secret"))
    try:
        return jwt.decode(token, signing_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token"
        ) from exc


def require_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token"
        )
    return _decode_token(credentials.credentials)


def issue_stream_ticket(session_id: str) -> tuple[str, datetime]:
    settings = get_settings()
    ticket = uuid.uuid4().hex
    expires = datetime.now(timezone.utc) + timedelta(
        seconds=settings.stream_ticket_ttl_seconds
    )
    firestore_client.create_document(
        STREAM_TICKETS_COLLECTION,
        ticket,
        {"session_id": session_id, "used": False, "expires_at_ticket": expires},
    )
    return ticket, expires


def consume_stream_ticket(ticket: str, session_id: str) -> bool:
    """One-time use: returns False if missing, already used, expired, or for
    the wrong session."""
    doc = firestore_client.get_document(STREAM_TICKETS_COLLECTION, ticket)
    if doc is None or doc.get("used"):
        return False
    if doc.get("session_id") != session_id:
        return False
    expires_at_ticket = doc.get("expires_at_ticket")
    if expires_at_ticket is not None and expires_at_ticket < datetime.now(timezone.utc):
        return False
    firestore_client.update_document(STREAM_TICKETS_COLLECTION, ticket, {"used": True})
    return True
