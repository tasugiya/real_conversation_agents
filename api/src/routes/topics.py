"""GET /v1/topics -- fixed dummy topic list. X API is not implemented yet
(docs/backend/03_AGENT_ORCHESTRATION_DRAFT.md §4; MVP-012 is a "Could", not "Must").
"""

from fastapi import APIRouter, Depends

from ..middleware.auth import require_access_token
from ..middleware.rate_limit import enforce_rate_limit
from ..schemas.topic_pack import Topic, TopicsResponse

router = APIRouter(prefix="/v1", tags=["topics"])

FIXED_TOPICS = [
    Topic(topic_id="campus_life", title="Campus life"),
    Topic(topic_id="weekend_plans", title="Weekend plans"),
    Topic(topic_id="favorite_media", title="Favorite movies or shows"),
]


@router.get(
    "/topics",
    response_model=TopicsResponse,
    dependencies=[Depends(enforce_rate_limit), Depends(require_access_token)],
)
async def list_topics() -> TopicsResponse:
    return TopicsResponse(topics=FIXED_TOPICS)
