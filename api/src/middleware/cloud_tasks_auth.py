"""Verify that a request to an /internal/* endpoint genuinely came from
Cloud Tasks.

Cloud Run's ingress/IAM protection is service-wide, not per-path. Since prod
otherwise allows unauthenticated access (docs/infra/03_SECURITY.md §3), this
application-level OIDC check is what actually protects internal endpoints
from being called directly by an end user.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from ..config import get_settings

_google_request = google_requests.Request()


async def require_cloud_tasks_oidc(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing OIDC token")

    token = authorization.removeprefix("Bearer ")
    try:
        claims = id_token.verify_oauth2_token(token, _google_request)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid OIDC token"
        ) from exc

    if claims.get("email") != settings.cloud_tasks_invoker_sa_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="unexpected invoker identity"
        )
