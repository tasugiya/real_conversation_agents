"""Secret Manager access (docs/infra/02_PARAMS_DEF.md §4).

Secrets are never cached across a long TTL in this module -- they're small
and infrequently read (only on auth / token-signing operations), so a short
in-process cache is a reasonable tradeoff against Secret Manager read cost.
"""

from functools import lru_cache

from google.cloud import secretmanager

from ..config import get_settings


@lru_cache
def _client() -> secretmanager.SecretManagerServiceClient:
    return secretmanager.SecretManagerServiceClient()


@lru_cache(maxsize=16)
def get_secret(secret_id: str, version: str = "latest") -> str:
    settings = get_settings()
    name = (
        f"projects/{settings.gcp_project_id}/secrets/{secret_id}/versions/{version}"
    )
    response = _client().access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8")
