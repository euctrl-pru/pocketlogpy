"""Connection functions: pl_connect and pl_connect_admin."""

import os
from typing import Optional

import requests

from ._utils import Connection


def pl_connect(
    url: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
) -> Connection:
    """Connect to PocketBase as a regular user.

    Authenticates against the ``users`` auth collection and returns a
    :class:`Connection` for use with all daily pocketlogpy functions.
    Credentials fall back to environment variables when not supplied.

    Parameters
    ----------
    url : str, optional
        PocketBase instance URL. Defaults to ``POCKETLOG_URL`` env var.
    email : str, optional
        Service account email. Defaults to ``POCKETLOG_EMAIL`` env var.
    password : str, optional
        Service account password. Defaults to ``POCKETLOG_PASSWORD`` env var.

    Returns
    -------
    Connection
        An authenticated connection object.

    Raises
    ------
    ValueError
        If any required parameter is missing.
    RuntimeError
        If authentication fails.

    Examples
    --------
    >>> conn = pl_connect()
    >>> conn = pl_connect(
    ...     url="https://myapp.pockethost.io",
    ...     email="service@example.com",
    ...     password="secret",
    ... )
    """
    url = url or os.environ.get("POCKETLOG_URL", "")
    email = email or os.environ.get("POCKETLOG_EMAIL", "")
    password = password or os.environ.get("POCKETLOG_PASSWORD", "")

    if not url:
        raise ValueError("PocketBase URL is required. Set POCKETLOG_URL or pass 'url'.")
    if not email:
        raise ValueError("Email is required. Set POCKETLOG_EMAIL or pass 'email'.")
    if not password:
        raise ValueError("Password is required. Set POCKETLOG_PASSWORD or pass 'password'.")

    url = url.rstrip("/")
    token = _auth(url, "users", email, password)
    print(f"Connected to PocketBase at {url}")
    return Connection(url, token)


def pl_connect_admin(
    url: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
) -> Connection:
    """Connect to PocketBase as a superuser (admin).

    Authenticates against the ``_superusers`` collection. Use this only for
    :func:`pl_setup`. Regular operations should use :func:`pl_connect`.

    Parameters
    ----------
    url : str, optional
        PocketBase instance URL. Defaults to ``POCKETLOG_URL`` env var.
    email : str, optional
        Superuser email. Defaults to ``POCKETLOG_ADMIN_EMAIL`` env var.
    password : str, optional
        Superuser password. Defaults to ``POCKETLOG_ADMIN_PASSWORD`` env var.

    Returns
    -------
    Connection
        An authenticated superuser connection object.

    Raises
    ------
    ValueError
        If any required parameter is missing.
    RuntimeError
        If authentication fails.

    Examples
    --------
    >>> conn_admin = pl_connect_admin()
    """
    url = url or os.environ.get("POCKETLOG_URL", "")
    email = email or os.environ.get("POCKETLOG_ADMIN_EMAIL", "")
    password = password or os.environ.get("POCKETLOG_ADMIN_PASSWORD", "")

    if not url:
        raise ValueError("PocketBase URL is required. Set POCKETLOG_URL or pass 'url'.")
    if not email:
        raise ValueError("Admin email is required. Set POCKETLOG_ADMIN_EMAIL or pass 'email'.")
    if not password:
        raise ValueError("Admin password is required. Set POCKETLOG_ADMIN_PASSWORD or pass 'password'.")

    url = url.rstrip("/")
    token = _auth(url, "_superusers", email, password)
    print(f"Connected to PocketBase (superuser) at {url}")
    return Connection(url, token)


def _auth(url: str, collection: str, email: str, password: str) -> str:
    endpoint = f"{url}/api/collections/{collection}/auth-with-password"
    resp = requests.post(endpoint, json={"identity": email, "password": password})
    if resp.status_code != 200:
        try:
            msg = resp.json().get("message", "Authentication failed")
        except Exception:
            msg = "Authentication failed"
        raise RuntimeError(f"Authentication failed ({resp.status_code}): {msg}")
    return resp.json()["token"]
