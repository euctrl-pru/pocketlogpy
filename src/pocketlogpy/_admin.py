"""Admin-only operations: pl_delete_flow and pl_delete_logs."""

import warnings
from datetime import datetime
from typing import List, Optional, Union

import requests

from ._utils import (
    Connection,
    VALID_STATUSES,
    _validate_conn,
    _headers,
    _format_timestamp,
)


def pl_delete_flow(
    conn: Connection,
    flow: str,
    force: bool = False,
) -> None:
    """Delete a flow (admin only).

    Requires a superuser connection. PocketBase enforces referential integrity,
    so any log entries referencing the flow must be deleted first. Use
    ``force=True`` to do this automatically.

    Parameters
    ----------
    conn : Connection
        A superuser connection from :func:`pl_connect_admin`.
    flow : str
        Flow name.
    force : bool, optional
        If ``True``, deletes all log entries for this flow before deleting the
        flow itself. If ``False`` (default), errors if log entries exist.

    Raises
    ------
    ValueError
        If the flow is not found.
    RuntimeError
        If deletion fails.

    Examples
    --------
    >>> conn_admin = pl_connect_admin()
    >>> pl_delete_flow(conn_admin, "old_flow", force=True)
    >>> pl_delete_flow(conn_admin, "empty_flow")
    """
    _validate_conn(conn)

    if not isinstance(flow, str) or not flow:
        raise ValueError("'flow' must be a non-empty string.")

    flows = _get_flows_raw_by_name(conn, flow)
    if not flows:
        raise ValueError(f"Flow '{flow}' not found.")
    flow_id = flows[0]["id"]

    if force:
        n_deleted = _delete_logs_for_flow(conn, flow_id)
        if n_deleted > 0:
            print(f"Deleted {n_deleted} log entr{'y' if n_deleted == 1 else 'ies'} for flow '{flow}'.")

    resp = requests.delete(
        f"{conn.url}/api/collections/pl_flows/records/{flow_id}",
        headers=_headers(conn),
    )

    if resp.status_code == 400:
        try:
            msg = resp.json().get("message", "")
        except Exception:
            msg = ""
        if "constraint" in msg.lower() or "relation" in msg.lower():
            raise RuntimeError(
                f"Flow '{flow}' has log entries. Use force=True to delete them first."
            )
        raise RuntimeError(f"Failed to delete flow '{flow}': {msg or resp.status_code}")

    if resp.status_code not in (200, 204):
        raise RuntimeError(
            f"Failed to delete flow '{flow}' (HTTP {resp.status_code}): {resp.text}"
        )

    print(f"Flow '{flow}' deleted.")


def pl_delete_logs(
    conn: Connection,
    flow: Optional[str] = None,
    before: Optional[Union[datetime, str]] = None,
    status: Optional[str] = None,
) -> int:
    """Delete log entries (admin only).

    All filter arguments are optional and combined with AND logic. Called
    with no filters, deletes all log entries.

    Parameters
    ----------
    conn : Connection
        A superuser connection from :func:`pl_connect_admin`.
    flow : str, optional
        If provided, only logs for that flow are deleted.
    before : datetime or str, optional
        If provided, only logs created before this timestamp are deleted.
    status : str, optional
        If provided, only logs with that status are deleted.
        One of ``"SUCCESS"``, ``"ERROR"``, or ``"FATAL"``.

    Returns
    -------
    int
        Number of deleted records.

    Examples
    --------
    >>> conn_admin = pl_connect_admin()
    >>> from datetime import datetime, timedelta, timezone
    >>> pl_delete_logs(conn_admin,
    ...                before=datetime.now(timezone.utc) - timedelta(days=30))
    >>> pl_delete_logs(conn_admin, flow="ectrl_data_load", status="ERROR")
    >>> pl_delete_logs(conn_admin, flow="old_flow")
    """
    _validate_conn(conn)

    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"'status' must be one of: {', '.join(VALID_STATUSES)}")

    filter_parts = []
    if flow is not None:
        filter_parts.append(f'flow.name = "{flow}"')
    if status is not None:
        filter_parts.append(f'status = "{status}"')
    if before is not None:
        filter_parts.append(f'created <= "{_format_timestamp(before)}"')
    filter_str = " && ".join(filter_parts) if filter_parts else None

    ids = _collect_log_ids(conn, filter_str)
    if not ids:
        print("No log entries matched — nothing deleted.")
        return 0

    for record_id in ids:
        resp = requests.delete(
            f"{conn.url}/api/collections/pl_logs/records/{record_id}",
            headers=_headers(conn),
        )
        if resp.status_code not in (200, 204):
            warnings.warn(
                f"Failed to delete log {record_id} (HTTP {resp.status_code}): {resp.text}",
                stacklevel=2,
            )

    count = len(ids)
    print(f"Deleted {count} log entr{'y' if count == 1 else 'ies'}.")
    return count


def _get_flows_raw_by_name(conn: Connection, flow_name: str) -> List[dict]:
    resp = requests.get(
        f"{conn.url}/api/collections/pl_flows/records",
        headers=_headers(conn),
        params={"filter": f'name = "{flow_name}"', "perPage": 1},
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def _collect_log_ids(
    conn: Connection, filter_str: Optional[str] = None
) -> List[str]:
    ids: List[str] = []
    page = 1
    while True:
        params = {"perPage": 200, "page": page, "fields": "id"}
        if filter_str:
            params["filter"] = filter_str
        resp = requests.get(
            f"{conn.url}/api/collections/pl_logs/records",
            headers=_headers(conn),
            params=params,
        )
        resp.raise_for_status()
        body = resp.json()
        ids.extend(item["id"] for item in body.get("items", []))
        if page >= body.get("totalPages", 1):
            break
        page += 1
    return ids


def _delete_logs_for_flow(conn: Connection, flow_id: str) -> int:
    ids = _collect_log_ids(conn, f'flow = "{flow_id}"')
    for record_id in ids:
        requests.delete(
            f"{conn.url}/api/collections/pl_logs/records/{record_id}",
            headers=_headers(conn),
        )
    return len(ids)
