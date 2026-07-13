"""X API v2 client for trending topics (GET /2/trends/by/woeid/{woeid}).

Falls back gracefully: if the bearer token is not configured or the API
call fails for any reason, callers receive an empty list and can use
fixed topics instead. No exception propagates outside this module.
"""

from __future__ import annotations

import logging
import time

import httpx

from ..services.secret_manager_client import get_secret

logger = logging.getLogger("x_client")

_X_API_BASE = "https://api.twitter.com/2"

# WOEID codes for regions. 1 = Worldwide.
WOEID_JAPAN = 23424856
WOEID_TOKYO = 1118370
WOEID_WORLDWIDE = 1

# In-process cache to cut down on paid X API calls (TODO.md P1 #11). Only
# successful responses are cached -- a missing token or a failed call is
# never cached, so fixing the token or a transient outage recovers on the
# very next call rather than being stuck for the TTL. Per-instance only,
# like rate_limit.py's bucket -- Cloud Run isn't sticky per client, so a
# cold/different instance just re-fetches; that's an acceptable tradeoff
# for a hackathon-scale deployment rather than a shared Firestore cache.
_TREND_CACHE_TTL_SECONDS = 30 * 60
_trend_cache: dict[int, tuple[float, list[dict]]] = {}


def _get_bearer_token(environment: str) -> str | None:
    try:
        return get_secret(f"x-api-bearer-token-{environment}")
    except Exception:
        return None


async def get_trends(woeid: int, environment: str) -> list[dict]:
    """Return a list of trending topic dicts: {"topic_id": str, "title": str, "source": "x"}.

    Returns empty list on any failure so callers can fallback to fixed topics.
    Successful results are cached per-woeid for _TREND_CACHE_TTL_SECONDS.
    """
    now = time.monotonic()
    cached = _trend_cache.get(woeid)
    if cached is not None and now - cached[0] < _TREND_CACHE_TTL_SECONDS:
        return cached[1]

    bearer_token = _get_bearer_token(environment)
    if not bearer_token:
        logger.info("x_client: no bearer token configured, skipping X trends")
        return []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_X_API_BASE}/trends/by/woeid/{woeid}",
                headers={"Authorization": f"Bearer {bearer_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("x_client: trends API failed: %s", exc)
        return []

    trends = []
    for item in data.get("data", []):
        name = item.get("trend_name") or item.get("name", "")
        if not name:
            continue
        trends.append({
            "topic_id": f"x_trend_{name.lower().replace(' ', '_').replace('#', '')}",
            "title": name,
            "source": "x",
            "tweet_count": item.get("tweet_count"),
        })
    _trend_cache[woeid] = (now, trends)
    return trends


async def search_recent(query: str, max_results: int, bearer_token: str) -> list[dict]:
    """Search recent tweets for a query. Returns list of tweet dicts."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{_X_API_BASE}/tweets/search/recent",
                params={
                    "query": f"{query} lang:en -is:retweet",
                    "max_results": min(max_results, 100),
                    "tweet.fields": "text,author_id,created_at,public_metrics",
                },
                headers={"Authorization": f"Bearer {bearer_token}"},
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
    except Exception as exc:
        logger.warning("x_client: recent search failed for %r: %s", query, exc)
        return []
