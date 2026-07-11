"""Cloud Run health checks. Deliberately unauthenticated (docs/infra/01_ARCHITECTURE.md §3.2)."""

from fastapi import APIRouter

from ..services import firestore_client

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> dict:
    try:
        firestore_client.get_client()
        firestore_ok = True
    except Exception:
        firestore_ok = False
    return {"status": "ok" if firestore_ok else "degraded", "firestore": firestore_ok}
