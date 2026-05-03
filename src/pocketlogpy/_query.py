"""Log query: pl_get_logs."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import requests

from ._utils import (
    Connection,
    VALID_STATUSES,
    _validate_conn,
    _headers,
    _format_timestamp,
)


def pl_get_logs(
    conn: Connection,
    flow: Optional[str] = None,
    status: Optional[str] = None,
    from_: Optional[Union[datetime, str]] = None,
    to: Optional[Union[datetime, str]] = None,
    limit: int = 50,
) -> List[Dict]:
    """Query log entries.

    All filter arguments are optional and combined with AND logic.

    Parameters
    ----------
    conn : Connection
        A connection object from :func:`pl_connect`.
    flow : str, optional
        Flow name to filter by.
    status : str, optional
        Status to filter by: ``"SUCCESS"``, ``"ERROR"``, or ``"FATAL"``.
    from_ : datetime or str, optional
        Start timestamp (inclusive).
    to : datetime or str, optional
        End timestamp (inclusive).
    limit : int, optional
        Maximum number of records to return. Default 50.

    Returns
    -------
    list of dict
        Each dict has keys: ``id``, ``flow``, ``log_type``, ``status``,
        ``message``, ``metadata``, ``created``.

    Examples
    --------
    >>> conn = pl_connect()
    >>> pl_get_logs(conn)
    >>> pl_get_logs(conn, flow="ectrl_data_load", status="ERROR")
    >>> from datetime import datetime, timedelta, timezone
    >>> pl_get_logs(conn,
    ...             from_=datetime.now(timezone.utc) - timedelta(days=1),
    ...             limit=100)
    """
    _validate_conn(conn)

    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"'status' must be one of: {', '.join(VALID_STATUSES)}")

    filter_parts = []
    if flow is not None:
        filter_parts.append(f'flow.name = "{flow}"')
    if status is not None:
        filter_parts.append(f'status = "{status}"')
    if from_ is not None:
        filter_parts.append(f'created >= "{_format_timestamp(from_)}"')
    if to is not None:
        filter_parts.append(f'created <= "{_format_timestamp(to)}"')
    filter_str = " && ".join(filter_parts) if filter_parts else None

    params: Dict[str, Any] = {"perPage": limit, "sort": "-id", "expand": "flow"}
    if filter_str:
        params["filter"] = filter_str

    resp = requests.get(
        f"{conn.url}/api/collections/pl_logs/records",
        headers=_headers(conn),
        params=params,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])

    return [
        {
            "id":       item.get("id"),
            "flow":     (item.get("expand", {}) or {}).get("flow", {}).get("name")
                        or item.get("flow"),
            "log_type": item.get("log_type"),
            "status":   item.get("status"),
            "message":  item.get("message"),
            "metadata": item.get("metadata"),
            "created":  item.get("created"),
        }
        for item in items
    ]
