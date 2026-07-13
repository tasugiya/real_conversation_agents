"""Best-effort container memory pressure detection via cgroup v2 (BUG-023).

Cloud Run exposes cgroup v2 memory accounting to the container process
(/sys/fs/cgroup/memory.current, /sys/fs/cgroup/memory.max). Reading these
directly avoids keeping an app-level memory-limit constant in sync with
infra/terraform's cloud_run_memory value -- whatever limit is actually
configured at deploy time is what gets compared against.

Fails open (returns None) on any read/parse error -- local dev without
cgroups, a different sandboxing setup, an unlimited cgroup, etc. must never
block session creation just because usage can't be determined.
"""

from __future__ import annotations

from pathlib import Path

_CGROUP_CURRENT = Path("/sys/fs/cgroup/memory.current")
_CGROUP_MAX = Path("/sys/fs/cgroup/memory.max")


def memory_usage_ratio() -> float | None:
    """Current cgroup memory usage as a fraction of the configured limit.

    Returns None if unavailable (no cgroup v2, no limit set, or any error)
    rather than raising -- callers should treat None as "unknown, proceed".
    """
    try:
        current = int(_CGROUP_CURRENT.read_text().strip())
        limit_raw = _CGROUP_MAX.read_text().strip()
        if limit_raw == "max":
            return None
        limit = int(limit_raw)
        if limit <= 0:
            return None
        return current / limit
    except (OSError, ValueError):
        return None
