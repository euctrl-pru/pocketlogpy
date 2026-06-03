from __future__ import annotations

import json
from typing import Any

import requests

from . import _utils


class PocketLogBase:
    """Shared HTTP infrastructure for PocketLog clients.

    Not intended for direct instantiation — use :class:`PocketLog` or
    :class:`PocketLogAdmin`.
    """

    def __init__(self, url: str, token: str) -> None:
        self._url = url.rstrip("/")
        self._token = token
        self._session = requests.Session()
        self._session.headers["Authorization"] = token

    @property
    def url(self) -> str:
        return self._url

    @property
    def token(self) -> str:
        return self._token

    # ── Authentication ───────────────────────────────────────────────────

    @staticmethod
    def _authenticate(url: str, collection: str, email: str, password: str) -> str:
        endpoint = f"{url}/api/collections/{collection}/auth-with-password"
        resp = requests.post(endpoint, json={"identity": email, "password": password})
        if resp.status_code != 200:
            body = {}
            try:
                body = resp.json()
            except Exception:
                pass
            msg = body.get("message", "Authentication failed")
            raise RuntimeError(
                f"Authentication failed ({resp.status_code}): {msg}"
            )
        return resp.json()["token"]

    # ── HTTP helpers ─────────────────────────────────────────────────────

    def _get(self, path: str, **params: Any) -> dict:
        resp = self._session.get(f"{self._url}/{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        resp = self._session.post(f"{self._url}/{path}", json=body)
        resp.raise_for_status()
        return resp.json()

    def _patch(self, path: str, body: dict) -> dict:
        resp = self._session.patch(f"{self._url}/{path}", json=body)
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str) -> requests.Response:
        resp = self._session.delete(f"{self._url}/{path}")
        return resp

    def _get_no_raise(self, path: str, **params: Any) -> requests.Response:
        return self._session.get(f"{self._url}/{path}", params=params)

    def _post_no_raise(self, path: str, body: dict) -> requests.Response:
        return self._session.post(f"{self._url}/{path}", json=body)

    def _delete_no_raise(self, path: str) -> requests.Response:
        return self._session.delete(f"{self._url}/{path}")

    # ── Flow resolution helpers ──────────────────────────────────────────

    def _resolve_flow_id(self, flow_name: str) -> str:
        params = {"filter": f'name = "{flow_name}"', "perPage": 1}
        body = self._get("api/collections/pl_flows/records", **params)
        if not body.get("items"):
            raise ValueError(f"Flow '{flow_name}' not found.")
        return body["items"][0]["id"]

    def _resolve_flow_ids(self, flow_names: list[str]) -> list[str]:
        return [self._resolve_flow_id(n) for n in flow_names]

    def _get_all_flows_raw(self) -> list[dict]:
        all_items: list[dict] = []
        page = 1
        while True:
            body = self._get(
                "api/collections/pl_flows/records", perPage=200, page=page
            )
            all_items.extend(body.get("items", []))
            if page >= body.get("totalPages", 1):
                break
            page += 1
        return all_items

    def _get_flows_raw_by_name(self, flow_name: str) -> list[dict]:
        params = {"filter": f'name = "{flow_name}"', "perPage": 1}
        body = self._get("api/collections/pl_flows/records", **params)
        return body.get("items", [])

    def _fetch_latest_log(
        self, flow_name: str, since: Any = None
    ) -> dict:
        filter_parts = [f'flow.name = "{flow_name}"']
        if since is not None:
            filter_parts.append(f'created >= "{_utils.format_timestamp(since)}"')
        filt = " && ".join(filter_parts)

        resp = self._get_no_raise(
            "api/collections/pl_logs/records",
            filter=filt,
            sort="-id",
            perPage=1,
        )
        if resp.status_code != 200:
            return {"status": None, "message": None, "created": None}
        body = resp.json()
        if not body.get("items"):
            return {"status": None, "message": None, "created": None}
        item = body["items"][0]
        return {
            "status": item.get("status"),
            "message": item.get("message"),
            "created": item.get("created"),
        }

    def _collect_log_ids(self, filter_str: str | None = None) -> list[str]:
        ids: list[str] = []
        page = 1
        while True:
            params: dict[str, Any] = {"perPage": 200, "page": page, "fields": "id"}
            if filter_str:
                params["filter"] = filter_str
            body = self._get("api/collections/pl_logs/records", **params)
            ids.extend(item["id"] for item in body.get("items", []))
            if page >= body.get("totalPages", 1):
                break
            page += 1
        return ids
