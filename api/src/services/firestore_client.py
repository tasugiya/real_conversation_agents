"""Firestore access (docs/infra/01_ARCHITECTURE.md §3.4, §6).

Collections: sessions, session_messages, reviews, topic_packs, display_events, jobs.
All documents carry expires_at; TTL policy is configured in Terraform
(infra/terraform/modules/firestore), not here.
"""

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from google.cloud import firestore

from ..config import get_settings

TTL_HOURS = 24


@lru_cache
def get_client() -> firestore.Client:
    settings = get_settings()
    return firestore.Client(
        project=settings.gcp_project_id,
        database=settings.firestore_database_id,
    )


def expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=TTL_HOURS)


def create_document(collection: str, doc_id: str, data: dict[str, Any]) -> None:
    data = {**data, "expires_at": expires_at()}
    get_client().collection(collection).document(doc_id).set(data)


def update_document(collection: str, doc_id: str, data: dict[str, Any]) -> None:
    get_client().collection(collection).document(doc_id).update(data)


def get_document(collection: str, doc_id: str) -> dict[str, Any] | None:
    snapshot = get_client().collection(collection).document(doc_id).get()
    return snapshot.to_dict() if snapshot.exists else None
