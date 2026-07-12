"""POST /v1/auth -- shared password login (docs/infra/03_SECURITY.md §2.1)."""

from fastapi import APIRouter, Depends, HTTPException, status

from ..middleware.app_check import require_app_check
from ..middleware.auth import issue_access_token, verify_password
from ..middleware.rate_limit import rate_limiter
from ..schemas.session import AuthRequest, AuthResponse

router = APIRouter(prefix="/v1", tags=["auth"])


@router.post("/auth", response_model=AuthResponse, dependencies=[Depends(rate_limiter("auth")), Depends(require_app_check)])
async def login(body: AuthRequest) -> AuthResponse:
    if not verify_password(body.username, body.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    token, expires_at = issue_access_token()
    return AuthResponse(access_token=token, expires_at=expires_at)
