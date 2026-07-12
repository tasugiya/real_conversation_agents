"""POST /v1/topic-packs, GET /v1/topic-packs/{id}, and the Cloud
Tasks-invoked internal generation endpoint (docs/infra/01_ARCHITECTURE.md §5).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from ..middleware.app_check import require_app_check
from ..middleware.auth import require_access_token
from ..middleware.cloud_tasks_auth import require_cloud_tasks_oidc
from ..middleware.rate_limit import rate_limiter
from ..schemas.topic_pack import (
    CreateTopicPackAcceptedResponse,
    CreateTopicPackRequest,
    TopicPack,
)
from ..services import firestore_client
from ..services.cloud_tasks_client import enqueue_topic_pack_generation
from ..tasks.topic_pack_generate import TOPIC_PACKS_COLLECTION
from ..tasks.topic_pack_generate import generate as generate_topic_pack

router = APIRouter(tags=["topic-packs"])


@router.post(
    "/v1/topic-packs",
    response_model=CreateTopicPackAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[
        Depends(rate_limiter("topic_packs")),
        Depends(require_access_token),
        Depends(require_app_check),
    ],
)
async def create_topic_pack(
    request: Request,
    body: CreateTopicPackRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> CreateTopicPackAcceptedResponse:
    """Avoids double-generation via the Idempotency-Key header
    (docs/backend/02_BACKEND_PROCESS_DRAFT.md §4.2)."""
    topic_pack_id = idempotency_key or uuid.uuid4().hex

    existing = firestore_client.get_document(TOPIC_PACKS_COLLECTION, topic_pack_id)
    if existing is None:
        firestore_client.create_document(
            TOPIC_PACKS_COLLECTION,
            topic_pack_id,
            {
                "topic_pack_id": topic_pack_id,
                "topic_id": body.topic_id,
                "status": "pending",
            },
        )
        enqueue_topic_pack_generation(
            topic_pack_id, body.topic_id, str(request.base_url),
            topic_title=body.topic_title,
        )

    return CreateTopicPackAcceptedResponse(job_id=topic_pack_id, topic_pack_id=topic_pack_id)


@router.get(
    "/v1/topic-packs/{topic_pack_id}",
    response_model=TopicPack,
    dependencies=[Depends(rate_limiter("topic_packs")), Depends(require_access_token)],
)
async def get_topic_pack(topic_pack_id: str) -> TopicPack:
    doc = firestore_client.get_document(TOPIC_PACKS_COLLECTION, topic_pack_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="topic pack not found")
    return TopicPack(**doc)


@router.post(
    "/internal/topic-packs/{topic_pack_id}/generate",
    include_in_schema=False,
    dependencies=[Depends(require_cloud_tasks_oidc)],
)
async def internal_generate_topic_pack(topic_pack_id: str, body: dict) -> dict:
    generate_topic_pack(
        topic_pack_id,
        body["topic_id"],
        topic_title=body.get("topic_title"),
    )
    return {"status": "ok"}
