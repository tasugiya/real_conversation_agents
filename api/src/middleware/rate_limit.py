"""Per-Cloud-Run-instance rate limiting (docs/infra/03_SECURITY.md §7).

Deliberately in-process, not shared across instances via Firestore/Redis:
Cloud Run instances are not sticky per client, so this is calibrated as
(desired global per-IP cap) / cloud_run_max_instances rather than an exact
global limit -- a simple, slightly loose bound rather than a precise one.
See config.py's rate_limit_per_ip_per_minute docstring.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from ..config import get_settings

_WINDOW_SECONDS = 60

# ip -> list of request timestamps within the current window
_hits: dict[str, list[float]] = defaultdict(list)


async def enforce_rate_limit(request: Request) -> None:
    settings = get_settings()
    limit = settings.rate_limit_per_ip_per_minute
    client_ip = request.client.host if request.client else "unknown"

    now = time.monotonic()
    window_start = now - _WINDOW_SECONDS
    hits = [t for t in _hits[client_ip] if t > window_start]

    if len(hits) >= limit:
        retry_after = int(_WINDOW_SECONDS - (now - hits[0]))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded",
            headers={"Retry-After": str(max(retry_after, 1))},
        )

    hits.append(now)
    _hits[client_ip] = hits
