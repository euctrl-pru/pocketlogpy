from __future__ import annotations

import json
import os
import warnings
from datetime import datetime
from typing import Any

from . import _utils
from ._base import PocketLogBase
from .constants import VALID_STATUSES
from .models import DagEntry, Dependency, Flow, LogEntry, StatusEntry


class PocketLog(PocketLogBase):
    """Client for daily pocketlogpy operations.

    Authenticates as a regular user against PocketBase.

    Parameters
    ----------
    url : str, optional
        PocketBase instance URL. Falls back to ``POCKETLOG_URL`` env var.
    email : str, optional
        Service account email. Falls back to ``POCKETLOG_EMAIL`` env var.
    password : str, optional
        Service account password. Falls back to ``POCKETLOG_PASSWORD`` env var.
    """

    def __init__(
        self,
        url: str | None = None,
        email: str | None = None,
        password: str | None = None,
    ) -> None:
        url = url or os.environ.get("POCKETLOG_URL", "")
        email = email or os.environ.get("POCKETLOG_EMAIL", "")
        password = password or os.environ.get("POCKETLOG_PASSWORD", "")

        if not url:
            raise ValueError(
                "PocketBase URL is required. Set POCKETLOG_URL or pass 'url'."
            )
        if not email:
            raise ValueError(
                "Email is required. Set POCKETLOG_EMAIL or pass 'email'."
            )
        if not password:
            raise ValueError(
                "Password is required. Set POCKETLOG_PASSWORD or pass 'password'."
            )

        url = url.rstrip("/")
        token = self._authenticate(url, "users", email, password)
        super().__init__(url, token)

    # ── Flow Management ──────────────────────────────────────────────────

    def create_flow(
        self,
        name: str,
        type: str,
        owner: str,
        description: str | None = None,
        schedule: str | None = None,
        metadata: dict | None = None,
        depends_on: list[str] | None = None,
    ) -> dict:
        """Register a new flow. Errors if a flow with the same name exists.

        Parameters
        ----------
        name : str
            Unique flow identifier.
        type : str
            Flow type string.
        owner : str
            Owner or responsible party.
        description : str, optional
            Human-readable description.
        schedule : str, optional
            Cron expression or human-readable schedule.
        metadata : dict, optional
            Arbitrary data, serialised to JSON.
        depends_on : list[str], optional
            Names of upstream flows.

        Returns
        -------
        dict
            The created flow record from PocketBase.
        """
        if not isinstance(name, str) or not name:
            raise ValueError("'name' must be a non-empty string.")
        if not isinstance(type, str) or not type:
            raise ValueError("'type' must be a non-empty string.")
        if not isinstance(owner, str) or not owner:
            raise ValueError("'owner' must be a non-empty string.")

        existing = self.get_flows(name=name)
        if existing:
            raise ValueError(f"A flow named '{name}' already exists.")

        dep_ids: list[str] = []
        if depends_on:
            all_flows_raw = self._get_all_flows_raw()
            if _utils.detect_cycle(name, depends_on, all_flows_raw):
                raise ValueError(
                    f"Adding dependency would create a cycle involving flow '{name}'."
                )
            dep_ids = self._resolve_flow_ids(depends_on)

        body: dict[str, Any] = {
            "name": name,
            "type": type,
            "owner": owner,
        }
        if description is not None:
            body["description"] = description
        if schedule is not None:
            body["schedule"] = schedule
        if metadata is not None:
            body["metadata"] = json.dumps(metadata)
        if dep_ids:
            body["depends_on"] = dep_ids

        return self._post("api/collections/pl_flows/records", body)

    def get_flows(
        self,
        type: str | None = None,
        name: str | None = None,
    ) -> list[Flow]:
        """Return a list of flows, optionally filtered.

        Parameters
        ----------
        type : str, optional
            Filter by flow type.
        name : str, optional
            Filter by flow name.

        Returns
        -------
        list[Flow]
        """
        filter_parts: list[str] = []
        if type is not None:
            filter_parts.append(f'type = "{type}"')
        if name is not None:
            filter_parts.append(f'name = "{name}"')
        filt = " && ".join(filter_parts) if filter_parts else None

        all_items: list[dict] = []
        page = 1
        while True:
            params: dict[str, Any] = {"perPage": 200, "page": page}
            if filt:
                params["filter"] = filt
            body = self._get("api/collections/pl_flows/records", **params)
            all_items.extend(body.get("items", []))
            if page >= body.get("totalPages", 1):
                break
            page += 1

        if not all_items:
            return []

        id_map = _utils.build_flow_name_map(all_items)

        result: list[Flow] = []
        for item in all_items:
            dep_ids = _utils.normalize_dep_ids(item.get("depends_on"))
            dep_names = [id_map.get(did, did) for did in dep_ids]
            meta = item.get("metadata")
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(
                Flow(
                    id=item.get("id", ""),
                    name=item.get("name", ""),
                    type=item.get("type", ""),
                    owner=item.get("owner", ""),
                    description=item.get("description"),
                    schedule=item.get("schedule"),
                    metadata=meta,
                    depends_on=dep_names,
                    created=item.get("created", ""),
                    updated=item.get("updated", ""),
                )
            )
        return result

    # ── Dependency Management ────────────────────────────────────────────

    def add_dependency(self, flow: str, depends_on: list[str]) -> dict:
        """Add upstream dependencies to an existing flow.

        Parameters
        ----------
        flow : str
            Name of the flow to update.
        depends_on : list[str]
            Upstream flow names to add.

        Returns
        -------
        dict
            The updated flow record.
        """
        if not isinstance(flow, str) or len(flow) == 0:
            raise ValueError("'flow' must be a single non-empty string.")
        if (
            not isinstance(depends_on, list)
            or len(depends_on) == 0
            or not all(isinstance(d, str) for d in depends_on)
        ):
            raise ValueError("'depends_on' must be a non-empty list of strings.")

        all_flows_raw = self._get_all_flows_raw()
        targets = [f for f in all_flows_raw if f["name"] == flow]
        if not targets:
            raise ValueError(f"Flow '{flow}' not found.")
        target = targets[0]

        id_map = _utils.build_flow_name_map(all_flows_raw)
        current_dep_ids = _utils.normalize_dep_ids(target.get("depends_on"))

        new_dep_ids = self._resolve_flow_ids(depends_on)

        current_dep_names = [id_map.get(did, did) for did in current_dep_ids]
        all_proposed_names = list(set(current_dep_names + depends_on))

        if _utils.detect_cycle(flow, all_proposed_names, all_flows_raw):
            raise ValueError(
                f"Adding dependency would create a cycle involving flow '{flow}'."
            )

        combined_ids = list(dict.fromkeys(current_dep_ids + new_dep_ids))
        return self._patch(
            f"api/collections/pl_flows/records/{target['id']}",
            {"depends_on": combined_ids},
        )

    def remove_dependency(self, flow: str, depends_on: list[str]) -> dict:
        """Remove upstream dependencies from a flow.

        Parameters
        ----------
        flow : str
            Name of the flow to update.
        depends_on : list[str]
            Upstream flow names to remove.

        Returns
        -------
        dict
            The updated flow record.
        """
        if not isinstance(flow, str) or len(flow) == 0:
            raise ValueError("'flow' must be a single non-empty string.")
        if (
            not isinstance(depends_on, list)
            or len(depends_on) == 0
            or not all(isinstance(d, str) for d in depends_on)
        ):
            raise ValueError("'depends_on' must be a non-empty list of strings.")

        all_flows_raw = self._get_all_flows_raw()
        targets = [f for f in all_flows_raw if f["name"] == flow]
        if not targets:
            raise ValueError(f"Flow '{flow}' not found.")
        target = targets[0]

        remove_ids = set(self._resolve_flow_ids(depends_on))
        current_dep_ids = _utils.normalize_dep_ids(target.get("depends_on"))
        remaining = [did for did in current_dep_ids if did not in remove_ids]

        return self._patch(
            f"api/collections/pl_flows/records/{target['id']}",
            {"depends_on": remaining},
        )

    def get_dependencies(
        self, flow: str, recursive: bool = False
    ) -> list[Dependency]:
        """Return upstream dependencies for a flow.

        Parameters
        ----------
        flow : str
            Flow name.
        recursive : bool
            If True, walk the full DAG upward returning all transitive
            dependencies. Default is direct only.

        Returns
        -------
        list[Dependency]
        """
        all_flows_raw = self._get_all_flows_raw()
        id_map = _utils.build_flow_name_map(all_flows_raw)
        name_to_flow = {f["name"]: f for f in all_flows_raw}

        target = name_to_flow.get(flow)
        if target is None:
            raise ValueError(f"Flow '{flow}' not found.")

        def _collect(flow_obj: dict, depth: int, visited: set[str]) -> list[Dependency]:
            dep_ids = _utils.normalize_dep_ids(flow_obj.get("depends_on"))
            rows: list[Dependency] = []
            for dep_id in dep_ids:
                dep_name = id_map.get(dep_id)
                if dep_name is None or dep_name in visited:
                    continue
                dep_flow = name_to_flow.get(dep_name)
                if dep_flow is None:
                    continue
                rows.append(
                    Dependency(
                        name=dep_name,
                        type=dep_flow.get("type", ""),
                        description=dep_flow.get("description"),
                        schedule=dep_flow.get("schedule"),
                        depth=depth,
                    )
                )
                if recursive:
                    rows.extend(_collect(dep_flow, depth + 1, visited | {dep_name}))
            return rows

        return _collect(target, 1, set())

    # ── Status & DAG ─────────────────────────────────────────────────────

    def get_status(
        self,
        flow: str,
        since: datetime | str | None = None,
    ) -> list[StatusEntry]:
        """Return the dependency chain health for a flow.

        Walks the DAG upward and collects the most recent log entry for
        each flow (including the target itself).

        Parameters
        ----------
        flow : str
            Flow name.
        since : datetime or str, optional
            Only consider logs after this timestamp.

        Returns
        -------
        list[StatusEntry]
            Sorted by depth then flow name.
        """
        all_flows_raw = self._get_all_flows_raw()
        id_map = _utils.build_flow_name_map(all_flows_raw)
        name_to_flow = {f["name"]: f for f in all_flows_raw}

        target = name_to_flow.get(flow)
        if target is None:
            raise ValueError(f"Flow '{flow}' not found.")

        def _collect_chain(
            flow_obj: dict, depth: int, visited: set[str]
        ) -> list[StatusEntry]:
            fname = flow_obj["name"]
            if fname in visited:
                return []
            visited = visited | {fname}

            latest = self._fetch_latest_log(fname, since)
            rows = [
                StatusEntry(
                    flow=fname,
                    type=flow_obj.get("type", ""),
                    status=latest.get("status"),
                    message=latest.get("message"),
                    created=latest.get("created"),
                    depth=depth,
                )
            ]
            dep_ids = _utils.normalize_dep_ids(flow_obj.get("depends_on"))
            for dep_id in dep_ids:
                dep_name = id_map.get(dep_id)
                if dep_name is None:
                    continue
                dep_flow = name_to_flow.get(dep_name)
                if dep_flow is None:
                    continue
                rows.extend(_collect_chain(dep_flow, depth + 1, visited))
            return rows

        entries = _collect_chain(target, 0, set())
        entries.sort(key=lambda e: (e.depth, e.flow))
        return entries

    def get_dag(
        self,
        since: datetime | str | None = None,
    ) -> list[DagEntry]:
        """Return a full DAG overview of all flows with effective status.

        A flow is *poisoned* if any upstream has an ERROR/FATAL log more
        recent than the flow's own last SUCCESS — meaning the flow ran
        successfully after the upstream had already broken.

        Parameters
        ----------
        since : datetime or str, optional
            Only consider logs after this timestamp.

        Returns
        -------
        list[DagEntry]
        """
        all_flows_raw = self._get_all_flows_raw()
        if not all_flows_raw:
            return []

        id_map = _utils.build_flow_name_map(all_flows_raw)
        name_to_flow = {f["name"]: f for f in all_flows_raw}

        latest_logs = {
            f["name"]: self._fetch_latest_log(f["name"], since)
            for f in all_flows_raw
        }

        def _get_all_upstream(flow_name: str, visited: set[str]) -> list[str]:
            f = name_to_flow.get(flow_name)
            if f is None:
                return []
            dep_ids = _utils.normalize_dep_ids(f.get("depends_on"))
            upstream: list[str] = []
            for dep_id in dep_ids:
                dep_name = id_map.get(dep_id)
                if dep_name is None or dep_name in visited:
                    continue
                upstream.append(dep_name)
                upstream.extend(
                    _get_all_upstream(dep_name, visited | {dep_name})
                )
            return list(dict.fromkeys(upstream))

        result: list[DagEntry] = []
        for f in all_flows_raw:
            fname = f["name"]
            log = latest_logs[fname]
            dep_ids = _utils.normalize_dep_ids(f.get("depends_on"))
            dep_names = [id_map.get(did, did) for did in dep_ids]

            raw_status = log.get("status")
            raw_status_time = log.get("created")
            is_root = len(dep_ids) == 0

            last_success_ts = None
            if raw_status == "SUCCESS" and raw_status_time:
                last_success_ts = _utils.parse_timestamp(raw_status_time)

            if raw_status is None:
                effective_status = None
                poisoned_by: list[str] = []
            elif raw_status in ("ERROR", "FATAL"):
                effective_status = raw_status
                poisoned_by = []
            else:
                all_upstream = _get_all_upstream(fname, set())
                poisoners: list[str] = []
                for up_name in all_upstream:
                    up_log = latest_logs.get(up_name, {})
                    up_status = up_log.get("status")
                    if up_status in ("ERROR", "FATAL"):
                        up_ts = _utils.parse_timestamp(up_log.get("created"))
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

            result.append(
                DagEntry(
                    flow=fname,
                    type=f.get("type", ""),
                    schedule=f.get("schedule"),
                    raw_status=raw_status,
                    raw_status_time=raw_status_time,
                    effective_status=effective_status,
                    poisoned_by=poisoned_by,
                    depends_on=dep_names,
                    is_root=is_root,
                )
            )
        return result

    # ── Logging ──────────────────────────────────────────────────────────

    def log(
        self,
        flow: str,
        status: str,
        log_type: str,
        message: str | None = None,
        metadata: dict | None = None,
        logged_by: str | None = None,
        logged_from: dict | None = None,
        source_file: str | None = None,
        source_repo: str | None = None,
    ) -> dict | None:
        """Record a log entry for a flow.

        On HTTP failure, retries up to 3 times with 2-second intervals.
        If all retries fail, emits a warning and returns ``None`` — the
        calling script is never stopped.

        Parameters
        ----------
        flow : str
            Flow name.
        status : str
            One of ``"SUCCESS"``, ``"ERROR"``, or ``"FATAL"``.
        log_type : str
            Free-text log type.
        message : str, optional
            Human-readable message.
        metadata : dict, optional
            Arbitrary data, serialised to JSON.
        logged_by : str, optional
            Username. Auto-detected if not provided.
        logged_from : dict, optional
            Machine context. Auto-detected if not provided.
        source_file : str, optional
            Script filename. Auto-detected if not provided.
        source_repo : str, optional
            Git repo name. Auto-detected if not provided.

        Returns
        -------
        dict or None
            Created log record, or None on failure.
        """
        if status not in VALID_STATUSES:
            raise ValueError(
                f"'status' must be one of: {', '.join(VALID_STATUSES)}"
            )
        if not isinstance(flow, str) or not flow:
            raise ValueError("'flow' must be a non-empty string.")
        if not isinstance(log_type, str) or not log_type:
            raise ValueError("'log_type' must be a non-empty string.")

        if logged_by is None:
            logged_by = _utils.get_system_user()
        if logged_from is None:
            logged_from = _utils.get_machine_info()
        if source_file is None:
            source_file = _utils.get_source_file()
        if source_repo is None:
            source_repo = _utils.get_source_repo()

        def _do_log() -> dict:
            flow_id = self._resolve_flow_id(flow)
            body: dict[str, Any] = {
                "flow": flow_id,
                "log_type": log_type,
                "status": status,
            }
            if message is not None:
                body["message"] = message
            if metadata is not None:
                body["metadata"] = json.dumps(metadata)
            if logged_by is not None:
                body["logged_by"] = logged_by
            if logged_from is not None:
                body["logged_from"] = json.dumps(logged_from)
            if source_file is not None:
                body["source_file"] = source_file
            if source_repo is not None:
                body["source_repo"] = source_repo
            return self._post("api/collections/pl_logs/records", body)

        result = _utils.retry(_do_log, times=3, wait=2)

        if isinstance(result, Exception):
            warnings.warn(
                f"pocketlogpy: failed to log event for flow '{flow}' "
                f"after 3 attempts: {result}",
                stacklevel=2,
            )
            return None
        return result

    def success(
        self,
        flow: str,
        log_type: str,
        message: str | None = None,
        metadata: dict | None = None,
        logged_by: str | None = None,
        logged_from: dict | None = None,
        source_file: str | None = None,
        source_repo: str | None = None,
    ) -> dict | None:
        """Log a SUCCESS event. Convenience wrapper around :meth:`log`."""
        return self.log(
            flow,
            "SUCCESS",
            log_type,
            message=message,
            metadata=metadata,
            logged_by=logged_by,
            logged_from=logged_from,
            source_file=source_file,
            source_repo=source_repo,
        )

    def error(
        self,
        flow: str,
        log_type: str,
        message: str | None = None,
        metadata: dict | None = None,
        logged_by: str | None = None,
        logged_from: dict | None = None,
        source_file: str | None = None,
        source_repo: str | None = None,
    ) -> dict | None:
        """Log an ERROR event. Convenience wrapper around :meth:`log`."""
        return self.log(
            flow,
            "ERROR",
            log_type,
            message=message,
            metadata=metadata,
            logged_by=logged_by,
            logged_from=logged_from,
            source_file=source_file,
            source_repo=source_repo,
        )

    def fatal(
        self,
        flow: str,
        log_type: str,
        message: str | None = None,
        metadata: dict | None = None,
        logged_by: str | None = None,
        logged_from: dict | None = None,
        source_file: str | None = None,
        source_repo: str | None = None,
    ) -> dict | None:
        """Log a FATAL event. Convenience wrapper around :meth:`log`."""
        return self.log(
            flow,
            "FATAL",
            log_type,
            message=message,
            metadata=metadata,
            logged_by=logged_by,
            logged_from=logged_from,
            source_file=source_file,
            source_repo=source_repo,
        )

    # ── Querying ─────────────────────────────────────────────────────────

    def get_logs(
        self,
        flow: str | None = None,
        status: str | None = None,
        from_: datetime | str | None = None,
        to: datetime | str | None = None,
        limit: int = 50,
    ) -> list[LogEntry]:
        """Query log entries.

        Parameters
        ----------
        flow : str, optional
            Filter by flow name.
        status : str, optional
            Filter by status (SUCCESS/ERROR/FATAL).
        from_ : datetime or str, optional
            Start timestamp.
        to : datetime or str, optional
            End timestamp.
        limit : int
            Maximum records to return. Default 50.

        Returns
        -------
        list[LogEntry]
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
        if from_ is not None:
            filter_parts.append(
                f'created >= "{_utils.format_timestamp(from_)}"'
            )
        if to is not None:
            filter_parts.append(
                f'created <= "{_utils.format_timestamp(to)}"'
            )
        filt = " && ".join(filter_parts) if filter_parts else None

        params: dict[str, Any] = {
            "perPage": limit,
            "sort": "-id",
            "expand": "flow",
        }
        if filt:
            params["filter"] = filt

        body = self._get("api/collections/pl_logs/records", **params)
        items = body.get("items", [])

        result: list[LogEntry] = []
        for item in items:
            flow_name = item.get("flow", "")
            expand = item.get("expand", {})
            if expand and "flow" in expand:
                flow_name = expand["flow"].get("name", flow_name)

            meta = item.get("metadata")
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    pass

            logged_from_val = item.get("logged_from")
            if isinstance(logged_from_val, str):
                try:
                    logged_from_val = json.loads(logged_from_val)
                except (json.JSONDecodeError, TypeError):
                    pass

            result.append(
                LogEntry(
                    id=item.get("id", ""),
                    flow=flow_name,
                    log_type=item.get("log_type", ""),
                    status=item.get("status", ""),
                    message=item.get("message"),
                    metadata=meta,
                    logged_by=item.get("logged_by"),
                    logged_from=logged_from_val,
                    source_file=item.get("source_file"),
                    source_repo=item.get("source_repo"),
                    created=item.get("created", ""),
                )
            )
        return result
