"""Internal utilities, constants, and the Connection class."""

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests


FLOW_TYPES: tuple = (
    "data_job",
    "website_status",
    "email_check",
    "db_check",
    "website_online",
)

LOG_TYPES: tuple = (
    "data_job",
    "website_online",
    "website_status",
    "email_check",
    "db_check",
)

VALID_STATUSES: tuple = ("SUCCESS", "ERROR", "FATAL")


class Connection:
    """Authenticated connection to a PocketBase instance.

    Obtain via :func:`pl_connect` or :func:`pl_connect_admin`.

    Attributes
    ----------
    url : str
        PocketBase instance base URL.
    token : str
        JWT auth token.
    """

    def __init__(self, url: str, token: str) -> None:
        self.url = url.rstrip("/")
        self.token = token

    def __repr__(self) -> str:
        return f"Connection(url={self.url!r})"


def _validate_conn(conn: Any) -> None:
    if not isinstance(conn, Connection):
        raise TypeError(
            "'conn' must be a Connection object. Use pl_connect() to create one."
        )


def _headers(conn: Connection) -> Dict[str, str]:
    return {"Authorization": conn.token}


def _format_timestamp(ts: Any) -> Optional[str]:
    """Format a datetime or string for use in PocketBase filter expressions."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    return str(ts)


def _parse_timestamp(ts_str: Optional[str]) -> Optional[datetime]:
    """Parse a PocketBase timestamp string to an aware UTC datetime."""
    if not ts_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(ts_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _norm_dep_ids(dep_ids: Any) -> List[str]:
    """Normalise depends_on from PocketBase (None / str / list) to a plain list."""
    if dep_ids is None:
        return []
    if isinstance(dep_ids, str):
        return [dep_ids] if dep_ids else []
    return [d for d in dep_ids if d]


def _build_flow_name_map(flows_raw: List[Dict]) -> Dict[str, str]:
    """Return {id: name} mapping from a list of raw flow records."""
    return {f["id"]: f["name"] for f in flows_raw if "id" in f and "name" in f}


def _get_all_flows_raw(conn: Connection) -> List[Dict]:
    """Fetch every record from pl_flows, handling pagination."""
    all_items: List[Dict] = []
    page = 1
    while True:
        resp = requests.get(
            f"{conn.url}/api/collections/pl_flows/records",
            headers=_headers(conn),
            params={"perPage": 200, "page": page},
        )
        resp.raise_for_status()
        body = resp.json()
        all_items.extend(body.get("items", []))
        if page >= body.get("totalPages", 1):
            break
        page += 1
    return all_items


def _resolve_flow_id(conn: Connection, flow_name: str) -> str:
    """Return the PocketBase record ID for a named flow."""
    resp = requests.get(
        f"{conn.url}/api/collections/pl_flows/records",
        headers=_headers(conn),
        params={"filter": f'name = "{flow_name}"', "perPage": 1},
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        raise ValueError(f"Flow '{flow_name}' not found.")
    return items[0]["id"]


def _resolve_flow_ids(conn: Connection, flow_names: List[str]) -> List[str]:
    """Resolve a list of flow names to their PocketBase record IDs."""
    return [_resolve_flow_id(conn, name) for name in flow_names]


def _detect_cycle(
    target_name: str,
    proposed_upstream_names: List[str],
    all_flows_raw: List[Dict],
) -> bool:
    """Return True if adding proposed_upstream_names as deps of target creates a cycle."""
    id_map = _build_flow_name_map(all_flows_raw)
    name_to_deps: Dict[str, List[str]] = {}
    for f in all_flows_raw:
        dep_ids = _norm_dep_ids(f.get("depends_on"))
        name_to_deps[f["name"]] = [id_map[d] for d in dep_ids if d in id_map]

    visited: set = set()
    stack = list(proposed_upstream_names)
    while stack:
        current = stack.pop(0)
        if current == target_name:
            return True
        if current in visited:
            continue
        visited.add(current)
        stack.extend(name_to_deps.get(current, []))
    return False


def _retry(func, times: int = 3, wait: float = 2.0):
    """Call func up to `times` times, sleeping `wait` seconds between failures."""
    last_exc = None
    for i in range(times):
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            if i < times - 1:
                time.sleep(wait)
    raise last_exc  # type: ignore[misc]
