from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Flow:
    """A registered flow in PocketBase."""

    id: str
    name: str
    type: str
    owner: str
    description: str | None = None
    schedule: str | None = None
    metadata: dict | None = None
    depends_on: list[str] = field(default_factory=list)
    created: str = ""
    updated: str = ""


@dataclass
class LogEntry:
    """A single log record returned by queries."""

    id: str
    flow: str
    log_type: str
    status: str
    message: str | None = None
    metadata: dict | None = None
    logged_by: str | None = None
    logged_from: dict | None = None
    source_file: str | None = None
    source_repo: str | None = None
    created: str = ""


@dataclass
class Dependency:
    """An upstream dependency of a flow."""

    name: str
    type: str
    description: str | None = None
    schedule: str | None = None
    depth: int = 1


@dataclass
class StatusEntry:
    """Health status of a single flow in the dependency chain."""

    flow: str
    type: str
    status: str | None = None
    message: str | None = None
    created: str | None = None
    depth: int = 0


@dataclass
class DagEntry:
    """Full DAG overview entry for a single flow."""

    flow: str
    type: str
    schedule: str | None = None
    raw_status: str | None = None
    raw_status_time: str | None = None
    effective_status: str | None = None
    poisoned_by: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    is_root: bool = True
