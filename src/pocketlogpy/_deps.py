"""Dependency management: add/remove deps, get_dependencies, get_status, get_dag."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import requests

from ._utils import (
    Connection,
    _validate_conn,
    _headers,
    _get_all_flows_raw,
    _norm_dep_ids,
    _build_flow_name_map,
    _detect_cycle,
    _resolve_flow_ids,
    _format_timestamp,
    _parse_timestamp,
)


def pl_add_dependency(
    conn: Connection,
    flow: str,
    depends_on: Union[str, List[str]],
) -> Dict:
    """Add upstream dependencies to a flow.

    Validates that all named flows exist and that no cycle would be created.

    Parameters
    ----------
    conn : Connection
        A connection object from :func:`pl_connect`.
    flow : str
        Name of the flow to update.
    depends_on : str or list of str
        Upstream flow name(s) to add.

    Returns
    -------
    dict
        The updated flow record.

    Examples
    --------
    >>> conn = pl_connect()
    >>> pl_add_dependency(conn, "ans_data_freshness", "another_upstream_flow")
    """
    _validate_conn(conn)

    if isinstance(depends_on, str):
        depends_on = [depends_on]
    if not depends_on:
        raise ValueError("'depends_on' must be a non-empty list of flow names.")

    all_flows_raw = _get_all_flows_raw(conn)
    id_map = _build_flow_name_map(all_flows_raw)
    target = next((f for f in all_flows_raw if f["name"] == flow), None)
    if target is None:
        raise ValueError(f"Flow '{flow}' not found.")

    current_dep_ids = _norm_dep_ids(target.get("depends_on"))
    current_dep_names = [id_map.get(d, d) for d in current_dep_ids]
    all_proposed = list(set(current_dep_names + list(depends_on)))

    if _detect_cycle(flow, all_proposed, all_flows_raw):
        raise ValueError(f"Adding dependency would create a cycle involving flow '{flow}'.")

    new_dep_ids = _resolve_flow_ids(conn, depends_on)
    combined_ids = list(set(current_dep_ids + new_dep_ids))

    resp = requests.patch(
        f"{conn.url}/api/collections/pl_flows/records/{target['id']}",
        headers=_headers(conn),
        json={"depends_on": combined_ids},
    )
    resp.raise_for_status()
    print(f"Dependencies updated for flow '{flow}'.")
    return resp.json()


def pl_remove_dependency(
    conn: Connection,
    flow: str,
    depends_on: Union[str, List[str]],
) -> Dict:
    """Remove upstream dependencies from a flow.

    Parameters
    ----------
    conn : Connection
        A connection object from :func:`pl_connect`.
    flow : str
        Name of the flow to update.
    depends_on : str or list of str
        Upstream flow name(s) to remove.

    Returns
    -------
    dict
        The updated flow record.

    Examples
    --------
    >>> conn = pl_connect()
    >>> pl_remove_dependency(conn, "ans_data_freshness", "another_upstream_flow")
    """
    _validate_conn(conn)

    if isinstance(depends_on, str):
        depends_on = [depends_on]
    if not depends_on:
        raise ValueError("'depends_on' must be a non-empty list of flow names.")

    all_flows_raw = _get_all_flows_raw(conn)
    target = next((f for f in all_flows_raw if f["name"] == flow), None)
    if target is None:
        raise ValueError(f"Flow '{flow}' not found.")

    remove_ids = set(_resolve_flow_ids(conn, depends_on))
    current_dep_ids = _norm_dep_ids(target.get("depends_on"))
    remaining_ids = [d for d in current_dep_ids if d not in remove_ids]

    resp = requests.patch(
        f"{conn.url}/api/collections/pl_flows/records/{target['id']}",
        headers=_headers(conn),
        json={"depends_on": remaining_ids},
    )
    resp.raise_for_status()
    print(f"Dependencies removed from flow '{flow}'.")
    return resp.json()


def pl_get_dependencies(
    conn: Connection,
    flow: str,
    recursive: bool = False,
) -> List[Dict]:
    """Get upstream dependencies of a flow.

    Parameters
    ----------
    conn : Connection
        A connection object from :func:`pl_connect`.
    flow : str
        Flow name.
    recursive : bool, optional
        If ``True``, walks the full DAG upward and returns all transitive
        upstream dependencies. If ``False`` (default), returns only direct
        (immediate) upstream dependencies.

    Returns
    -------
    list of dict
        Each dict has keys: ``name``, ``type``, ``description``, ``schedule``, ``depth``.

    Examples
    --------
    >>> conn = pl_connect()
    >>> pl_get_dependencies(conn, "ans_monthly_update")
    >>> pl_get_dependencies(conn, "ans_monthly_update", recursive=True)
    """
    _validate_conn(conn)

    all_flows_raw = _get_all_flows_raw(conn)
    id_map = _build_flow_name_map(all_flows_raw)
    name_to_flow = {f["name"]: f for f in all_flows_raw}

    target = name_to_flow.get(flow)
    if target is None:
        raise ValueError(f"Flow '{flow}' not found.")

    def collect_deps(flow_obj: Dict, depth: int, visited: set) -> List[Dict]:
        dep_ids = _norm_dep_ids(flow_obj.get("depends_on"))
        rows: List[Dict] = []
        for dep_id in dep_ids:
            dep_name = id_map.get(dep_id)
            if dep_name is None or dep_name in visited:
                continue
            dep_flow = name_to_flow.get(dep_name)
            if dep_flow is None:
                continue
            rows.append({
                "name":        dep_name,
                "type":        dep_flow.get("type"),
                "description": dep_flow.get("description"),
                "schedule":    dep_flow.get("schedule"),
                "depth":       depth,
            })
            if recursive:
                rows.extend(collect_deps(dep_flow, depth + 1, visited | {dep_name}))
        return rows

    return collect_deps(target, 1, set())


def pl_get_status(
    conn: Connection,
    flow: str,
    since: Optional[Union[datetime, str]] = None,
) -> List[Dict]:
    """Get dependency chain health status for a flow.

    Walks the DAG upward recursively and collects the most recent log entry
    for each flow in the chain, including the flow itself.

    Parameters
    ----------
    conn : Connection
        A connection object from :func:`pl_connect`.
    flow : str
        Flow name.
    since : datetime or str, optional
        If provided, only log entries created after this timestamp are
        considered. Flows with no logs since that time get ``status=None``.

    Returns
    -------
    list of dict
        Sorted by depth then flow name. Each dict has keys:
        ``flow``, ``type``, ``status``, ``message``, ``created``, ``depth``.

    Examples
    --------
    >>> conn = pl_connect()
    >>> pl_get_status(conn, "ans_monthly_update")
    >>> from datetime import datetime, timedelta, timezone
    >>> pl_get_status(conn, "ans_monthly_update",
    ...               since=datetime.now(timezone.utc) - timedelta(days=1))
    """
    _validate_conn(conn)

    all_flows_raw = _get_all_flows_raw(conn)
    id_map = _build_flow_name_map(all_flows_raw)
    name_to_flow = {f["name"]: f for f in all_flows_raw}

    target = name_to_flow.get(flow)
    if target is None:
        raise ValueError(f"Flow '{flow}' not found.")

    def collect_chain(flow_obj: Dict, depth: int, visited: set) -> List[Dict]:
        fname = flow_obj["name"]
        if fname in visited:
            return []
        visited = visited | {fname}
        latest_log = _fetch_latest_log(conn, fname, since)
        rows: List[Dict] = [{
            "flow":    fname,
            "type":    flow_obj.get("type"),
            "status":  latest_log.get("status"),
            "message": latest_log.get("message"),
            "created": latest_log.get("created"),
            "depth":   depth,
        }]
        dep_ids = _norm_dep_ids(flow_obj.get("depends_on"))
        for dep_id in dep_ids:
            dep_name = id_map.get(dep_id)
            if dep_name is None:
                continue
            dep_flow = name_to_flow.get(dep_name)
            if dep_flow is None:
                continue
            rows.extend(collect_chain(dep_flow, depth + 1, visited))
        return rows

    rows = collect_chain(target, 0, set())
    return sorted(rows, key=lambda r: (r["depth"], r["flow"] or ""))


def pl_get_dag(
    conn: Connection,
    since: Optional[Union[datetime, str]] = None,
) -> List[Dict]:
    """Get a full DAG overview of all flows and their health.

    Returns every flow with its raw (most recent log) status and
    cascade-aware effective status. A flow is ``POISONED`` if any upstream
    dependency has a more recent ERROR/FATAL than the flow's own last SUCCESS,
    meaning its last result is stale.

    Parameters
    ----------
    conn : Connection
        A connection object from :func:`pl_connect`.
    since : datetime or str, optional
        If provided, only considers log entries created after this timestamp.

    Returns
    -------
    list of dict
        Each dict has keys: ``flow``, ``type``, ``schedule``, ``raw_status``,
        ``raw_status_time``, ``effective_status``, ``poisoned_by`` (list),
        ``depends_on`` (list), ``is_root``.

    Examples
    --------
    >>> conn = pl_connect()
    >>> dag = pl_get_dag(conn)
    >>> for row in dag:
    ...     print(row["flow"], row["effective_status"])
    """
    _validate_conn(conn)

    all_flows_raw = _get_all_flows_raw(conn)
    if not all_flows_raw:
        return []

    id_map = _build_flow_name_map(all_flows_raw)
    name_to_flow = {f["name"]: f for f in all_flows_raw}

    latest_logs = {
        f["name"]: _fetch_latest_log(conn, f["name"], since)
        for f in all_flows_raw
    }

    def get_all_upstream(flow_name: str, visited: set) -> List[str]:
        f = name_to_flow.get(flow_name)
        if f is None:
            return []
        dep_ids = _norm_dep_ids(f.get("depends_on"))
        upstream: List[str] = []
        for dep_id in dep_ids:
            dep_name = id_map.get(dep_id)
            if dep_name is None or dep_name in visited:
                continue
            upstream.append(dep_name)
            upstream.extend(get_all_upstream(dep_name, visited | {dep_name}))
        return list(set(upstream))

    rows = []
    for f in all_flows_raw:
        fname = f["name"]
        log = latest_logs[fname]
        dep_ids = _norm_dep_ids(f.get("depends_on"))
        dep_names = [id_map.get(d, d) for d in dep_ids]

        raw_status = log.get("status")
        raw_status_time = log.get("created")
        is_root = len(dep_ids) == 0

        last_success_ts = None
        if raw_status == "SUCCESS":
            last_success_ts = _parse_timestamp(raw_status_time)

        if raw_status is None:
            effective_status = None
            poisoned_by: List[str] = []
        elif raw_status in ("ERROR", "FATAL"):
            effective_status = raw_status
            poisoned_by = []
        else:
            all_upstream = get_all_upstream(fname, set())
            poisoners: List[str] = []
            for up_name in all_upstream:
                up_log = latest_logs.get(up_name, {})
                up_status = up_log.get("status")
                if up_status in ("ERROR", "FATAL"):
                    up_ts = _parse_timestamp(up_log.get("created"))
                    if (
                        last_success_ts is not None
                        and up_ts is not None
                        and last_success_ts > up_ts
                    ):
                        poisoners.append(up_name)
            if poisoners:
                effective_status = "POISONED"
                poisoned_by = poisoners
            else:
                effective_status = raw_status
                poisoned_by = []

        rows.append({
            "flow":             fname,
            "type":             f.get("type"),
            "schedule":         f.get("schedule"),
            "raw_status":       raw_status,
            "raw_status_time":  raw_status_time,
            "effective_status": effective_status,
            "poisoned_by":      poisoned_by,
            "depends_on":       dep_names,
            "is_root":          is_root,
        })
    return rows


def _fetch_latest_log(
    conn: Connection,
    flow_name: str,
    since: Optional[Union[datetime, str]] = None,
) -> Dict:
    filter_parts = [f'flow.name = "{flow_name}"']
    if since is not None:
        filter_parts.append(f'created >= "{_format_timestamp(since)}"')
    filter_str = " && ".join(filter_parts)

    resp = requests.get(
        f"{conn.url}/api/collections/pl_logs/records",
        headers=_headers(conn),
        params={"filter": filter_str, "sort": "-id", "perPage": 1},
    )
    if resp.status_code != 200:
        return {}
    items = resp.json().get("items", [])
    if not items:
        return {}
    item = items[0]
    return {
        "status":  item.get("status"),
        "message": item.get("message"),
        "created": item.get("created"),
    }
