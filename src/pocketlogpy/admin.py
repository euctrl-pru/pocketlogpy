from __future__ import annotations

import os
import warnings
from datetime import datetime
from typing import Any

from . import _utils
from ._base import PocketLogBase
from .constants import VALID_STATUSES


class PocketLogAdmin(PocketLogBase):
    """Admin client for setup and administrative operations.

    Authenticates as a superuser against PocketBase.

    Parameters
    ----------
    url : str, optional
        PocketBase instance URL. Falls back to ``POCKETLOG_URL`` env var.
    email : str, optional
        Superuser email. Falls back to ``POCKETLOG_ADMIN_EMAIL`` env var.
    password : str, optional
        Superuser password. Falls back to ``POCKETLOG_ADMIN_PASSWORD`` env var.
    """

    def __init__(
        self,
        url: str | None = None,
        email: str | None = None,
        password: str | None = None,
    ) -> None:
        url = url or os.environ.get("POCKETLOG_URL", "")
        email = email or os.environ.get("POCKETLOG_ADMIN_EMAIL", "")
        password = password or os.environ.get("POCKETLOG_ADMIN_PASSWORD", "")

        if not url:
            raise ValueError(
                "PocketBase URL is required. Set POCKETLOG_URL or pass 'url'."
            )
        if not email:
            raise ValueError(
                "Admin email is required. Set POCKETLOG_ADMIN_EMAIL or pass 'email'."
            )
        if not password:
            raise ValueError(
                "Admin password is required. Set POCKETLOG_ADMIN_PASSWORD or pass 'password'."
            )

        url = url.rstrip("/")
        token = self._authenticate(url, "_superusers", email, password)
        super().__init__(url, token)

    # ── Setup ────────────────────────────────────────────────────────────

    def setup(self) -> None:
        """Create ``pl_flows`` and ``pl_logs`` collections if they don't exist.

        Idempotent — safe to call multiple times.
        """
        existing = self._list_collections()
        existing_names = {c["name"] for c in existing}

        if "pl_flows" not in existing_names:
            self._create_flows_collection()

        if "pl_logs" not in existing_names:
            self._create_logs_collection()

    # ── Admin Operations ─────────────────────────────────────────────────

    def delete_flow(self, flow: str, force: bool = False) -> None:
        """Delete a flow by name.

        PocketBase enforces referential integrity — the call fails if log
        entries reference the flow. Use ``force=True`` to delete logs first.

        Parameters
        ----------
        flow : str
            Flow name.
        force : bool
            If True, delete all log entries for the flow first.
        """
        if not isinstance(flow, str) or not flow:
            raise ValueError("'flow' must be a non-empty string.")

        flows = self._get_flows_raw_by_name(flow)
        if not flows:
            raise ValueError(f"Flow '{flow}' not found.")
        flow_id = flows[0]["id"]

        if force:
            self._delete_logs_for_flow(flow_id)

        resp = self._delete_no_raise(
            f"api/collections/pl_flows/records/{flow_id}"
        )

        if resp.status_code == 400:
            body: dict = {}
            try:
                body = resp.json()
            except Exception:
                pass
            msg = body.get("message", "")
            if "constraint" in msg.lower() or "relation" in msg.lower():
                raise RuntimeError(
                    f"Flow '{flow}' has log entries. Use force=True to delete them first."
                )
            raise RuntimeError(
                f"Failed to delete flow '{flow}': {msg or resp.status_code}"
            )

        if resp.status_code not in (200, 204):
            raise RuntimeError(
                f"Failed to delete flow '{flow}' (HTTP {resp.status_code})"
            )

    def delete_logs(
        self,
        flow: str | None = None,
        before: datetime | str | None = None,
        status: str | None = None,
    ) -> int:
        """Delete log entries matching the given filters.

        All arguments are optional and combined with AND logic. Called with
        no filters, deletes **all** log entries.

        Parameters
        ----------
        flow : str, optional
            Only delete logs for this flow.
        before : datetime or str, optional
            Only delete logs created before this timestamp.
        status : str, optional
            Only delete logs with this status.

        Returns
        -------
        int
            Number of deleted records.
        """
        if status is not None and status not in VALID_STATUSES:
            raise ValueError(
                f"'status' must be one of: {', '.join(VALID_STATUSES)}"
            )

        filter_parts: list[str] = []
        if flow is not None:
            filter_parts.append(f'flow.name = "{flow}"')
        if status is not None:
            filter_parts.append(f'status = "{status}"')
        if before is not None:
            filter_parts.append(
                f'created <= "{_utils.format_timestamp(before)}"'
            )
        filt = " && ".join(filter_parts) if filter_parts else None

        ids = self._collect_log_ids(filt)
        if not ids:
            return 0

        for log_id in ids:
            resp = self._delete_no_raise(
                f"api/collections/pl_logs/records/{log_id}"
            )
            if resp.status_code not in (200, 204):
                warnings.warn(
                    f"Failed to delete log {log_id} (HTTP {resp.status_code})",
                    stacklevel=2,
                )

        return len(ids)

    # ── Internal Helpers ─────────────────────────────────────────────────

    def _list_collections(self) -> list[dict]:
        body = self._get("api/collections", perPage=200)
        return body.get("items", [])

    def _create_flows_collection(self) -> dict:
        body: dict[str, Any] = {
            "name": "pl_flows",
            "type": "base",
            "fields": [
                {"name": "name", "type": "text", "required": True},
                {"name": "description", "type": "text", "required": False},
                {"name": "type", "type": "text", "required": True},
                {"name": "schedule", "type": "text", "required": False},
                {"name": "owner", "type": "text", "required": True},
                {"name": "metadata", "type": "json", "required": False},
            ],
            "listRule": '@request.auth.id != ""',
            "viewRule": '@request.auth.id != ""',
            "createRule": '@request.auth.id != ""',
            "updateRule": '@request.auth.id != ""',
            "deleteRule": None,
        }

        resp = self._post_no_raise("api/collections", body)
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Failed to create pl_flows collection (HTTP {resp.status_code}): "
                f"{resp.text}"
            )
        col = resp.json()
        col_id = col["id"]

        patch_body = {
            "fields": col["fields"]
            + [
                {
                    "name": "depends_on",
                    "type": "relation",
                    "required": False,
                    "maxSelect": 999,
                    "collectionId": col_id,
                    "cascadeDelete": False,
                }
            ]
        }
        patch_resp = self._session.patch(
            f"{self._url}/api/collections/{col_id}", json=patch_body
        )
        if patch_resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Failed to add depends_on field to pl_flows "
                f"(HTTP {patch_resp.status_code}): {patch_resp.text}"
            )
        return patch_resp.json()

    def _create_logs_collection(self) -> dict:
        collections = self._list_collections()
        flows_col = [c for c in collections if c["name"] == "pl_flows"]
        if not flows_col:
            raise RuntimeError(
                "pl_flows collection must be created before pl_logs."
            )
        flows_col_id = flows_col[0]["id"]

        body: dict[str, Any] = {
            "name": "pl_logs",
            "type": "base",
            "fields": [
                {
                    "name": "flow",
                    "type": "relation",
                    "required": True,
                    "maxSelect": 1,
                    "collectionId": flows_col_id,
                    "cascadeDelete": False,
                },
                {"name": "log_type", "type": "text", "required": True},
                {"name": "status", "type": "text", "required": True},
                {"name": "message", "type": "text", "required": False},
                {"name": "metadata", "type": "json", "required": False},
                {"name": "logged_by", "type": "text", "required": False},
                {"name": "logged_from", "type": "json", "required": False},
                {"name": "source_file", "type": "text", "required": False},
                {"name": "source_repo", "type": "text", "required": False},
                {
                    "name": "created",
                    "type": "autodate",
                    "onCreate": True,
                    "onUpdate": False,
                },
            ],
            "listRule": '@request.auth.id != ""',
            "viewRule": '@request.auth.id != ""',
            "createRule": '@request.auth.id != ""',
            "updateRule": None,
            "deleteRule": None,
        }

        resp = self._post_no_raise("api/collections", body)
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Failed to create pl_logs collection (HTTP {resp.status_code}): "
                f"{resp.text}"
            )
        return resp.json()

    def _delete_logs_for_flow(self, flow_id: str) -> int:
        filter_str = f'flow = "{flow_id}"'
        ids = self._collect_log_ids(filter_str)
        for log_id in ids:
            self._delete_no_raise(f"api/collections/pl_logs/records/{log_id}")
        return len(ids)
