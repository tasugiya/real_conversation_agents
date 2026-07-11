"""Firebase App Check token verification (docs/infra/03_SECURITY.md §2.3).

APP_CHECK_ENFORCEMENT_MODE="monitor" logs failures without rejecting the
request, for staged rollout. Set to "enforce" once verified working.
"""

from __future__ import annotations

import logging

import firebase_admin
from fastapi import Header, HTTPException, status
from firebase_admin import app_check

from ..config import get_settings

logger = logging.getLogger("app_check")

_initialized = False


def _ensure_init() -> None:
    global _initialized
    if _initialized:
        return
    settings = get_settings()
    firebase_admin.initialize_app(options={"projectId": settings.firebase_project_id})
    _initialized = True


async def require_app_check(x_firebase_appcheck: str | None = Header(default=None)) -> None:
    """REST dependency. For the WebSocket route, call verify_app_check_token()
    directly instead -- FastAPI's Depends()-based header injection doesn't
    apply the same way to websocket routes."""
    await verify_app_check_token(x_firebase_appcheck)


async def verify_app_check_token(token: str | None) -> None:
    _ensure_init()

    if token is None:
        _handle_failure("missing X-Firebase-AppCheck header")
        return

    try:
        app_check.verify_token(token)
    except Exception as exc:  # noqa: BLE001 -- any verification failure is handled the same way
        _handle_failure(f"app check verification failed: {exc}")


def _handle_failure(reason: str) -> None:
    settings = get_settings()
    if settings.app_check_enforcement_mode == "enforce":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="app check failed")
    logger.warning("app_check.monitor_mode_failure: %s", reason)
