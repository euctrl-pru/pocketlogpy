from __future__ import annotations

import getpass
import inspect
import os
import platform
import re
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def detect_cycle(
    target_name: str,
    proposed_upstream_names: list[str],
    all_flows_raw: list[dict],
) -> bool:
    """Return True if adding *proposed_upstream_names* as dependencies of
    *target_name* would create a cycle in the DAG."""
    id_map = build_flow_name_map(all_flows_raw)
    name_to_deps: dict[str, list[str]] = {}
    for f in all_flows_raw:
        dep_ids = normalize_dep_ids(f.get("depends_on"))
        dep_names = [id_map[did] for did in dep_ids if did in id_map]
        name_to_deps[f["name"]] = dep_names

    visited: set[str] = set()
    stack = list(proposed_upstream_names)

    while stack:
        current = stack.pop(0)
        if current == target_name:
            return True
        if current in visited:
            continue
        visited.add(current)
        upstream = name_to_deps.get(current, [])
        stack.extend(upstream)

    return False


def normalize_dep_ids(dep_ids: Any) -> list[str]:
    """Normalise PocketBase dependency IDs to a plain list of non-empty strings."""
    if dep_ids is None:
        return []
    if isinstance(dep_ids, str):
        return [dep_ids] if dep_ids else []
    result: list[str] = []
    for item in dep_ids:
        s = str(item)
        if s:
            result.append(s)
    return result


def build_flow_name_map(flows_raw: list[dict]) -> dict[str, str]:
    """Build an ``{id: name}`` mapping from raw flow records."""
    return {f["id"]: f["name"] for f in flows_raw}


def build_filter(*parts: str | None) -> str | None:
    """Combine non-None filter parts with `` && ``."""
    non_null = [p for p in parts if p is not None]
    if not non_null:
        return None
    return " && ".join(non_null)


def format_timestamp(ts: datetime | str | None) -> str | None:
    """Format a timestamp for PocketBase filters."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        utc = ts.astimezone(timezone.utc) if ts.tzinfo else ts
        return utc.strftime("%Y-%m-%d %H:%M:%S")
    return str(ts)


def retry(fn: Callable[[], T], times: int = 3, wait: float = 2) -> T | Exception:
    """Call *fn* up to *times*, sleeping *wait* seconds between attempts.
    Returns the result on success, or the last exception on failure."""
    last_error: Exception | None = None
    for i in range(times):
        try:
            return fn()
        except Exception as exc:
            last_error = exc
            if i < times - 1:
                time.sleep(wait)
    return last_error  # type: ignore[return-value]


def get_system_user() -> str | None:
    """Detect the current OS username, or *None* if undetectable."""
    try:
        user = getpass.getuser()
        if user:
            return user
    except Exception:
        pass
    for var in ("USER", "USERNAME"):
        user = os.environ.get(var, "")
        if user:
            return user
    return None


def get_machine_info() -> dict[str, str | None]:
    """Return a dict with machine context: hostname, OS, version, user."""
    return {
        "machine": platform.node() or None,
        "os": platform.system() or None,
        "os_version": platform.release() or None,
        "user": get_system_user(),
    }


def get_source_file() -> str | None:
    """Walk the call stack to find the source filename of the caller."""
    for frame_info in inspect.stack():
        filename = frame_info.filename
        if filename and not filename.startswith("<") and os.path.isfile(filename):
            basename = os.path.basename(filename)
            if basename not in ("_utils.py", "client.py", "_base.py", "admin.py"):
                return basename
    return None


def get_source_repo() -> str | None:
    """Detect the git repo name from ``git remote get-url origin``."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        url = result.stdout.strip()
        if url:
            name = os.path.basename(url)
            return re.sub(r"\.git$", "", name)
    except Exception:
        pass
    return None


def parse_timestamp(ts_str: str | None) -> datetime | None:
    """Parse a PocketBase timestamp string to a datetime, or None."""
    if not ts_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%fZ", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(ts_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
