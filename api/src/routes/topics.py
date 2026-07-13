"""GET /v1/topics -- X API trending topics merged with fixed fallback topics.

X Trends (by WOEID) are fetched if a bearer token is configured.
On any failure the endpoint still returns the fixed topics, so
the conversation flow is never blocked by X API availability.
"""

from fastapi import APIRouter, Depends, Query

from ..config import get_settings
from ..middleware.auth import require_access_token
from ..middleware.rate_limit import rate_limiter
from ..schemas.topic_pack import Topic, TopicsResponse
from ..services import x_client

router = APIRouter(prefix="/v1", tags=["topics"])

# Fixed fallback topics (5 items per MEMO.md §1.2)
_FIXED_TOPICS: list[Topic] = [
    Topic(topic_id="campus_life", title="Campus life and making friends"),
    Topic(topic_id="food_culture", title="Food culture and local favorites"),
    Topic(topic_id="travel_trouble", title="Travel trouble and asking for help"),
    Topic(topic_id="ai_daily_life", title="AI tools in daily life"),
    Topic(topic_id="work_study", title="Work style and study habits"),
]

_WOEID_MAP = {
    "japan": x_client.WOEID_JAPAN,
    "tokyo": x_client.WOEID_TOKYO,
    "worldwide": x_client.WOEID_WORLDWIDE,
}

_MAX_X_TRENDS = 5


@router.get(
    "/topics",
    response_model=TopicsResponse,
    dependencies=[Depends(rate_limiter("topics")), Depends(require_access_token)],
)
async def list_topics(
    region: str = Query(default="japan", description="X Trends region: japan | tokyo | worldwide"),
) -> TopicsResponse:
    settings = get_settings()
    woeid = _WOEID_MAP.get(region.lower(), x_client.WOEID_JAPAN)

    x_trends = await x_client.get_trends(woeid=woeid, environment=settings.environment)

    # Deduplicate by topic_id; X trends first, fixed topics fill the rest
    seen: set[str] = set()
    topics: list[Topic] = []

    for raw in x_trends[:_MAX_X_TRENDS]:
        t = Topic(topic_id=raw["topic_id"], title=raw["title"])
        if t.topic_id not in seen:
            seen.add(t.topic_id)
            topics.append(t)

    for fixed in _FIXED_TOPICS:
        if fixed.topic_id not in seen:
            seen.add(fixed.topic_id)
            topics.append(fixed)

    return TopicsResponse(topics=topics)
