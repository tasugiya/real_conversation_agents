"""Environment configuration. Values documented in docs/infra/02_PARAMS_DEF.md §3."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gcp_project_id: str = ""
    gcp_region: str = "us-central1"
    environment: str = "dev"

    firestore_database_id: str = "(default)"
    agent_engine_resource_name: str = ""

    # The Cloud Tasks callback URL is derived from the incoming request at
    # runtime (see routes/topic_packs.py), not configured statically here --
    # a Cloud Run service can't reference its own URL in its own env vars
    # without a circular Terraform dependency.
    cloud_tasks_queue_name: str = ""
    cloud_tasks_invoker_sa_email: str = ""

    cors_allowed_origins: str = "*"

    auth_token_ttl_seconds: int = 3600
    stream_ticket_ttl_seconds: int = 60
    session_max_duration_seconds: int = 600
    max_concurrent_sessions: int = 5

    # Fraction of the container's cgroup memory.max above which create_session
    # proactively 503s instead of risking an OOM-kill mid-conversation
    # (BUG-023). See services/memory_monitor.py.
    memory_pressure_threshold: float = 0.85

    # per Cloud Run instance, not global -- see docs/infra/03_SECURITY.md §7.
    # Cloud Run requests are not sticky to one instance, so this should be
    # set to roughly (desired global per-IP cap) / cloud_run_max_instances.
    rate_limit_per_ip_per_minute: int = 20
    cloud_run_max_instances: int = 2

    app_check_enforcement_mode: str = "monitor"  # "monitor" or "enforce"
    firebase_project_id: str = ""

    log_level: str = "info"


@lru_cache
def get_settings() -> Settings:
    return Settings()
