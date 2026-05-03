"""Flow management: create and list flows."""

import json
from typing import Any, Dict, List, Optional

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
)


def pl_create_flow(
    conn: Connection,
    name: str,
    type: str,
    owner: str,
    description: Optional[str] = None,
    schedule: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    depends_on: Optional[List[str]] = None,
) -> Dict:
    """Register a new flow in PocketBase.

    Errors if a flow with the same name already exists. Validates that
    ``depends_on`` flows exist and that adding them would not create a cycle.

    Parameters
    ----------
    conn : Connection
        A connection object from :func:`pl_connect`.
    name : str
        Unique flow identifier (e.g. ``"ectrl_data_load"``).
    type : str
        Flow type string. See :data:`FLOW_TYPES` for defaults; any string accepted.
    owner : str
        Free-text owner or responsible party (e.g. ``"quinten"``, ``"team-data"``).
    description : str, optional
        Human-readable description.
    schedule : str, optional
        Cron expression or human-readable schedule string.
    metadata : dict, optional
        Arbitrary dict serialised to JSON.
    depends_on : list of str, optional
        Upstream flow names.

    Returns
    -------
    dict
        The created flow record.

    Examples
    --------
    >>> conn = pl_connect()
    >>> pl_create_flow(conn, "ectrl_data_load", type="data_job", owner="quinten",
    ...                description="Daily EUROCONTROL data import",
    ...                schedule="0 6 * * *")
    """
    _validate_conn(conn)

    if not isinstance(name, str) or not name:
        raise ValueError("'name' must be a non-empty string.")
    if not isinstance(type, str) or not type:
        raise ValueError("'type' must be a non-empty string.")
    if not isinstance(owner, str) or not owner:
        raise ValueError("'owner' must be a non-empty string.")

    existing = pl_get_flows(conn, name=name)
    if existing:
        raise ValueError(f"A flow named '{name}' already exists.")

    dep_ids: List[str] = []
    if depends_on:
        all_flows_raw = _get_all_flows_raw(conn)
        if _detect_cycle(name, depends_on, all_flows_raw):
            raise ValueError(
                f"Adding dependency would create a cycle involving flow '{name}'."
            )
        dep_ids = _resolve_flow_ids(conn, depends_on)

    body: Dict[str, Any] = {
        "name":       name,
        "type":       type,
        "owner":      owner,
        "depends_on": dep_ids,
    }
    if description is not None:
        body["description"] = description
    if schedule is not None:
        body["schedule"] = schedule
    if metadata is not None:
        body["metadata"] = json.dumps(metadata)

    resp = requests.post(
        f"{conn.url}/api/collections/pl_flows/records",
        headers=_headers(conn),
        json=body,
    )
    resp.raise_for_status()
    print(f"Flow '{name}' created.")
    return resp.json()


def pl_get_flows(
    conn: Connection,
    type: Optional[str] = None,
    name: Optional[str] = None,
) -> List[Dict]:
    """List flows, optionally filtered by name or type.

    Parameters
    ----------
    conn : Connection
        A connection object from :func:`pl_connect`.
    type : str, optional
        Filter by flow type.
    name : str, optional
        Filter by exact flow name.

    Returns
    -------
    list of dict
        Each dict has keys: ``id``, ``name``, ``type``, ``description``,
        ``schedule``, ``owner``, ``metadata``, ``depends_on`` (list of upstream
        flow names), ``created``, ``updated``.

    Examples
    --------
    >>> conn = pl_connect()
    >>> pl_get_flows(conn)
    >>> pl_get_flows(conn, type="data_job")
    >>> pl_get_flows(conn, name="ectrl_data_load")
    """
    _validate_conn(conn)

    filter_parts = []
    if type is not None:
        filter_parts.append(f'type = "{type}"')
    if name is not None:
        filter_parts.append(f'name = "{name}"')
    filter_str = " && ".join(filter_parts) if filter_parts else None

    all_items = []
    page = 1
    while True:
        params: Dict[str, Any] = {"perPage": 200, "page": page}
        if filter_str:
            params["filter"] = filter_str
        resp = requests.get(
            f"{conn.url}/api/collections/pl_flows/records",
            headers=_headers(conn),
            params=params,
        )
        resp.raise_for_status()
        body = resp.json()
        all_items.extend(body.get("items", []))
        if page >= body.get("totalPages", 1):
            break
        page += 1

    if not all_items:
        return []

    id_map = _build_flow_name_map(all_items)

    rows = []
    for item in all_items:
        dep_ids = _norm_dep_ids(item.get("depends_on"))
        dep_names = [id_map.get(d, d) for d in dep_ids]
        rows.append({
            "id":          item.get("id"),
            "name":        item.get("name"),
            "type":        item.get("type"),
            "description": item.get("description"),
            "schedule":    item.get("schedule"),
            "owner":       item.get("owner"),
            "metadata":    item.get("metadata"),
            "depends_on":  dep_names,
            "created":     item.get("created"),
            "updated":     item.get("updated"),
        })
    return rows
