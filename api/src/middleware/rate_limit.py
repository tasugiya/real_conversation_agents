"""Per-Cloud-Run-instance rate limiting (docs/infra/03_SECURITY.md §7).

Deliberately in-process, not shared across instances via Firestore/Redis:
Cloud Run instances are not sticky per client, so this is calibrated as
(desired global per-IP cap) / cloud_run_max_instances rather than an exact
global limit -- a simple, slightly loose bound rather than a precise one.
See config.py's rate_limit_per_ip_per_minute docstring.

client_ip is read from request.client.host, which already reflects the real
client address: uvicorn runs with --proxy-headers --forwarded-allow-ips='*'
(see Dockerfile), so its ProxyHeadersMiddleware rewrites scope["client"] from
X-Forwarded-For before this ever runs -- no header parsing needed here.

Buckets are keyed by (client_ip, category), not just client_ip (BUG-021 fix):
a single shared bucket meant WS-reconnect ticket churn (create_stream_ticket,
called on every reconnect attempt) could exhaust the same quota that
end_session/retry_review needed, causing review generation to 429 before it
ever ran even though the user never touched a review endpoint themselves.
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status

from ..config import get_settings

_WINDOW_SECONDS = 60

# (ip, category) -> list of request timestamps within the current window
_hits: dict[tuple[str, str], list[float]] = defaultdict(list)


def rate_limiter(category: str) -> Callable[[Request], Awaitable[None]]:
    """Build a rate-limit dependency scoped to `category` (e.g. "session_setup",
    "stream_ticket", "review") so unrelated traffic can't starve each other's
    quota. Each category gets its own independent per-IP allowance.
    """

    async def _enforce(request: Request) -> None:
        settings = get_settings()
        limit = settings.rate_limit_per_ip_per_minute
        client_ip = request.client.host if request.client else "unknown"
        key = (client_ip, category)

        now = time.monotonic()
        window_start = now - _WINDOW_SECONDS
        hits = [t for t in _hits[key] if t > window_start]

        if len(hits) >= limit:
            retry_after = int(_WINDOW_SECONDS - (now - hits[0]))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate limit exceeded",
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        hits.append(now)
        _hits[key] = hits

        # Evict stale keys periodically to prevent unbounded growth (BUG-009 fix).
        # One-in-100 chance per request keeps amortized cost negligible.
        if len(_hits) > 1000 and (int(now) % 100 == 0):
            stale = [k for k, ts in _hits.items() if not any(t > window_start for t in ts)]
            for k in stale:
                del _hits[k]

    return _enforce
