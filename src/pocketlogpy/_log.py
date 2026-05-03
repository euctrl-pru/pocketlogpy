"""Logging functions: pl_log, pl_success, pl_error, pl_fatal."""

import json
import warnings
from typing import Any, Dict, Optional

import requests

from ._utils import (
    Connection,
    VALID_STATUSES,
    _validate_conn,
    _headers,
    _resolve_flow_id,
    _retry,
)


def pl_log(
    conn: Connection,
    flow: str,
    status: str,
    log_type: str,
    message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict]:
    """Log an event for a flow.

    Records a log entry for the named flow. On HTTP failure, retries up to
    3 times with 2-second intervals. If all retries fail, emits a warning
    and returns ``None`` — the calling script is never stopped.

    Parameters
    ----------
    conn : Connection
        A connection object from :func:`pl_connect`.
    flow : str
        Flow name.
    status : str
        One of ``"SUCCESS"``, ``"ERROR"``, or ``"FATAL"``.
    log_type : str
        Free-text log type (e.g. ``"data_job"``, ``"website_online"``).
        See :data:`LOG_TYPES` for standard values; any string accepted.
    message : str, optional
        Human-readable log message.
    metadata : dict, optional
        Arbitrary dict serialised to JSON.

    Returns
    -------
    dict or None
        The created log record, or ``None`` on failure.

    Examples
    --------
    >>> conn = pl_connect()
    >>> pl_log(conn, "ectrl_data_load", "SUCCESS", log_type="data_job",
    ...        message="Loaded 14230 rows",
    ...        metadata={"rows": 14230, "duration_s": 45.2})
    """
    _validate_conn(conn)

    if status not in VALID_STATUSES:
        raise ValueError(f"'status' must be one of: {', '.join(VALID_STATUSES)}")
    if not isinstance(flow, str) or not flow:
        raise ValueError("'flow' must be a non-empty string.")
    if not isinstance(log_type, str) or not log_type:
        raise ValueError("'log_type' must be a non-empty string.")

    def _do_log():
        flow_id = _resolve_flow_id(conn, flow)
        body: Dict[str, Any] = {
            "flow":     flow_id,
            "log_type": log_type,
            "status":   status,
        }
        if message is not None:
            body["message"] = message
        if metadata is not None:
            body["metadata"] = json.dumps(metadata)
        resp = requests.post(
            f"{conn.url}/api/collections/pl_logs/records",
            headers=_headers(conn),
            json=body,
        )
        resp.raise_for_status()
        return resp.json()

    try:
        return _retry(_do_log, times=3, wait=2)
    except Exception as exc:
        warnings.warn(
            f"pocketlogpy: failed to log event for flow '{flow}' after 3 attempts: {exc}",
            stacklevel=2,
        )
        return None


def pl_success(
    conn: Connection,
    flow: str,
    log_type: str,
    message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict]:
    """Log a SUCCESS event.

    Convenience wrapper around :func:`pl_log` for successful outcomes.

    Parameters
    ----------
    conn : Connection
        A connection object from :func:`pl_connect`.
    flow : str
        Flow name.
    log_type : str
        Free-text log type. See :data:`LOG_TYPES` for standard values.
    message : str, optional
        Human-readable log message.
    metadata : dict, optional
        Arbitrary dict serialised to JSON.

    Returns
    -------
    dict or None
        The created log record, or ``None`` on failure.

    Examples
    --------
    >>> pl_success(conn, "ectrl_data_load", log_type="data_job",
    ...            message="Loaded 14230 rows", metadata={"rows": 14230})
    """
    return pl_log(conn, flow, "SUCCESS", log_type=log_type, message=message, metadata=metadata)


def pl_error(
    conn: Connection,
    flow: str,
    log_type: str,
    message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict]:
    """Log an ERROR event.

    Convenience wrapper around :func:`pl_log` for recoverable errors.

    Parameters
    ----------
    conn : Connection
        A connection object from :func:`pl_connect`.
    flow : str
        Flow name.
    log_type : str
        Free-text log type. See :data:`LOG_TYPES` for standard values.
    message : str, optional
        Human-readable log message.
    metadata : dict, optional
        Arbitrary dict serialised to JSON.

    Returns
    -------
    dict or None
        The created log record, or ``None`` on failure.

    Examples
    --------
    >>> pl_error(conn, "ans_website_online", log_type="website_online",
    ...          message="HTTP 503 returned", metadata={"http_status": 503})
    """
    return pl_log(conn, flow, "ERROR", log_type=log_type, message=message, metadata=metadata)


def pl_fatal(
    conn: Connection,
    flow: str,
    log_type: str,
    message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict]:
    """Log a FATAL event.

    Convenience wrapper around :func:`pl_log` for unrecoverable failures.

    Parameters
    ----------
    conn : Connection
        A connection object from :func:`pl_connect`.
    flow : str
        Flow name.
    log_type : str
        Free-text log type. See :data:`LOG_TYPES` for standard values.
    message : str, optional
        Human-readable log message.
    metadata : dict, optional
        Arbitrary dict serialised to JSON.

    Returns
    -------
    dict or None
        The created log record, or ``None`` on failure.

    Examples
    --------
    >>> pl_fatal(conn, "ectrl_data_load", log_type="data_job",
    ...          message="Unrecoverable database error")
    """
    return pl_log(conn, flow, "FATAL", log_type=log_type, message=message, metadata=metadata)
