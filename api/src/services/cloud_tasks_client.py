"""Enqueue Cloud Tasks HTTP tasks targeting this same Cloud Run service's own
internal endpoint. No separate Worker service exists
(docs/infra/01_ARCHITECTURE.md §5, docs/infra/04_DEPLOY.md).
"""

from __future__ import annotations

import json
from functools import lru_cache

from google.cloud import tasks_v2

from ..config import get_settings


@lru_cache
def _client() -> tasks_v2.CloudTasksClient:
    return tasks_v2.CloudTasksClient()


def enqueue_topic_pack_generation(
    topic_pack_id: str,
    topic_id: str,
    base_url: str,
    *,
    topic_title: str | None = None,
) -> None:
    """base_url is derived from the inbound request (e.g. str(request.base_url))
    by the caller, not read from static config -- see config.py's comment on
    why (a Cloud Run service can't reference its own URL in its own env vars)."""
    settings = get_settings()
    parent = _client().queue_path(
        settings.gcp_project_id, settings.gcp_region, settings.cloud_tasks_queue_name
    )

    body: dict = {"topic_id": topic_id}
    if topic_title:
        body["topic_title"] = topic_title

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{base_url.rstrip('/')}/internal/topic-packs/{topic_pack_id}/generate",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body).encode("utf-8"),
            "oidc_token": {
                "service_account_email": settings.cloud_tasks_invoker_sa_email,
            },
        }
    }
    _client().create_task(request={"parent": parent, "task": task})
