"""POST /v1/auth -- shared password login (docs/infra/03_SECURITY.md §2.1).

prod is intentionally login-free (2026-07-13 product decision): it's a public
demo, so the password layer is dropped there and App Check (enforce) +
per-IP rate limiting (rate_limiter("auth")) remain as its defense. This
reuses the existing `environment` setting rather than adding a dedicated
toggle env var.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from ..config import get_settings
from ..middleware.app_check import require_app_check
from ..middleware.auth import issue_access_token, verify_password
from ..middleware.rate_limit import rate_limiter
from ..schemas.session import AuthRequest, AuthResponse

router = APIRouter(prefix="/v1", tags=["auth"])


@router.post("/auth", response_model=AuthResponse, dependencies=[Depends(rate_limiter("auth")), Depends(require_app_check)])
async def login(body: AuthRequest) -> AuthResponse:
    if get_settings().environment != "prod" and not verify_password(body.username, body.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    token, expires_at = issue_access_token()
    return AuthResponse(access_token=token, expires_at=expires_at)
