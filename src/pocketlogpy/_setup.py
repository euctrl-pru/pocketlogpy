"""One-time PocketBase collection setup."""

import requests

from ._utils import Connection, _validate_conn, _headers


def pl_setup(conn: Connection) -> None:
    """Set up pocketlogpy collections in PocketBase.

    Creates the ``pl_flows`` and ``pl_logs`` collections with the correct schema
    and API rules. Requires a superuser connection from :func:`pl_connect_admin`.
    This function is idempotent — safe to call multiple times.

    Parameters
    ----------
    conn : Connection
        A superuser connection object from :func:`pl_connect_admin`.

    Raises
    ------
    RuntimeError
        If collection creation fails.

    Examples
    --------
    >>> conn_admin = pl_connect_admin()
    >>> pl_setup(conn_admin)
    """
    _validate_conn(conn)
    existing = _list_collections(conn)
    existing_names = {c["name"] for c in existing}

    if "pl_flows" not in existing_names:
        print("Creating collection pl_flows...")
        _create_flows_collection(conn)
        print("Collection pl_flows created.")
    else:
        print("Collection pl_flows already exists, skipping.")

    if "pl_logs" not in existing_names:
        print("Creating collection pl_logs...")
        _create_logs_collection(conn)
        print("Collection pl_logs created.")
    else:
        print("Collection pl_logs already exists, skipping.")

    print("pocketlogpy setup complete.")


def _list_collections(conn: Connection) -> list:
    resp = requests.get(
        f"{conn.url}/api/collections",
        headers=_headers(conn),
        params={"perPage": 200},
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def _create_flows_collection(conn: Connection) -> dict:
    body = {
        "name": "pl_flows",
        "type": "base",
        "fields": [
            {"name": "name",        "type": "text", "required": True},
            {"name": "description", "type": "text", "required": False},
            {"name": "type",        "type": "text", "required": True},
            {"name": "schedule",    "type": "text", "required": False},
            {"name": "owner",       "type": "text", "required": True},
            {"name": "metadata",    "type": "json", "required": False},
        ],
        "listRule":   '@request.auth.id != ""',
        "viewRule":   '@request.auth.id != ""',
        "createRule": '@request.auth.id != ""',
        "updateRule": '@request.auth.id != ""',
        "deleteRule": None,
    }
    resp = requests.post(
        f"{conn.url}/api/collections",
        headers=_headers(conn),
        json=body,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to create pl_flows collection (HTTP {resp.status_code}): {resp.text}"
        )
    col = resp.json()
    col_id = col["id"]

    patch_body = {
        "fields": col["fields"] + [
            {
                "name":          "depends_on",
                "type":          "relation",
                "required":      False,
                "maxSelect":     999,
                "collectionId":  col_id,
                "cascadeDelete": False,
            }
        ]
    }
    patch_resp = requests.patch(
        f"{conn.url}/api/collections/{col_id}",
        headers=_headers(conn),
        json=patch_body,
    )
    if patch_resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to add depends_on field to pl_flows "
            f"(HTTP {patch_resp.status_code}): {patch_resp.text}"
        )
    return patch_resp.json()


def _create_logs_collection(conn: Connection) -> dict:
    collections = _list_collections(conn)
    flows_col = next((c for c in collections if c["name"] == "pl_flows"), None)
    if flows_col is None:
        raise RuntimeError("pl_flows collection must be created before pl_logs.")
    flows_col_id = flows_col["id"]

    body = {
        "name": "pl_logs",
        "type": "base",
        "fields": [
            {
                "name":          "flow",
                "type":          "relation",
                "required":      True,
                "maxSelect":     1,
                "collectionId":  flows_col_id,
                "cascadeDelete": False,
            },
            {"name": "log_type", "type": "text",     "required": True},
            {"name": "status",   "type": "text",     "required": True},
            {"name": "message",  "type": "text",     "required": False},
            {"name": "metadata", "type": "json",     "required": False},
            {"name": "created",  "type": "autodate", "onCreate": True, "onUpdate": False},
        ],
        "listRule":   '@request.auth.id != ""',
        "viewRule":   '@request.auth.id != ""',
        "createRule": '@request.auth.id != ""',
        "updateRule": None,
        "deleteRule": None,
    }
    resp = requests.post(
        f"{conn.url}/api/collections",
        headers=_headers(conn),
        json=body,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to create pl_logs collection (HTTP {resp.status_code}): {resp.text}"
        )
    return resp.json()
