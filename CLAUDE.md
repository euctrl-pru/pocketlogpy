# CLAUDE.md — pocketlogpy

## Project Overview

`pocketlogpy` is a Python package that logs application events (data jobs, website monitoring, email checks, database checks, etc.) to a PocketBase instance hosted on PocketHost. It is the Python mirror of `pocketlogR`, redesigned with a class-oriented API. All functionality is feature-equivalent to the R package.

## Package Identity

- **Name:** `pocketlogpy`
- **Language:** Python (3.10+)
- **License:** MIT
- **Distribution:** pip installable via `pyproject.toml`
- **HTTP backend:** `requests`
- **API style:** Class-oriented with two main classes (`PocketLog`, `PocketLogAdmin`)

---

## Architecture

### Class Hierarchy

```
PocketLogBase (internal)
├── PocketLog      — daily operations (regular user auth)
└── PocketLogAdmin — setup & admin operations (superuser auth)
```

- **`PocketLogBase`** (`_base.py`): Shared HTTP infrastructure, authentication, flow resolution helpers. Not exported.
- **`PocketLog`** (`client.py`): All daily operations — flow management, logging, querying, dependency management, status/DAG inspection.
- **`PocketLogAdmin`** (`admin.py`): Setup (collection creation) and admin operations (delete flow, delete logs).

### Data Models

Return types use `dataclasses` instead of raw dicts:
- `Flow` — flow record
- `LogEntry` — log record
- `Dependency` — upstream dependency
- `StatusEntry` — chain health entry
- `DagEntry` — full DAG overview entry

### Module Map

```
src/pocketlogpy/
├── __init__.py      # Public exports
├── constants.py     # FLOW_TYPES, LOG_TYPES, VALID_STATUSES
├── models.py        # Dataclass definitions
├── _utils.py        # Standalone utilities (cycle detection, auto-detection, retry, filters)
├── _base.py         # PocketLogBase — shared HTTP + auth
├── client.py        # PocketLog class
└── admin.py         # PocketLogAdmin class
```

---

## Mapping from pocketlogR

| R function | Python equivalent |
|---|---|
| `pl_connect()` | `PocketLog(url, email, password)` |
| `pl_connect_admin()` | `PocketLogAdmin(url, email, password)` |
| `pl_setup(conn)` | `admin.setup()` |
| `pl_create_flow(conn, ...)` | `pl.create_flow(...)` |
| `pl_get_flows(conn, ...)` | `pl.get_flows(...)` |
| `pl_add_dependency(conn, ...)` | `pl.add_dependency(...)` |
| `pl_remove_dependency(conn, ...)` | `pl.remove_dependency(...)` |
| `pl_get_dependencies(conn, ...)` | `pl.get_dependencies(...)` |
| `pl_get_status(conn, ...)` | `pl.get_status(...)` |
| `pl_get_dag(conn, ...)` | `pl.get_dag(...)` |
| `pl_log(conn, ...)` | `pl.log(...)` |
| `pl_success(conn, ...)` | `pl.success(...)` |
| `pl_error(conn, ...)` | `pl.error(...)` |
| `pl_fatal(conn, ...)` | `pl.fatal(...)` |
| `pl_get_logs(conn, ...)` | `pl.get_logs(...)` |
| `pl_delete_flow(conn, ...)` | `admin.delete_flow(...)` |
| `pl_delete_logs(conn, ...)` | `admin.delete_logs(...)` |
| `pl_flow_types` | `FLOW_TYPES` |
| `pl_log_types` | `LOG_TYPES` |
| `.valid_statuses` | `VALID_STATUSES` |

---

## Authentication

### Two auth modes

1. **Regular user** (`PocketLog`): authenticates against `/api/collections/users/auth-with-password`. Used for all daily operations.
2. **Superuser** (`PocketLogAdmin`): authenticates against `/api/collections/_superusers/auth-with-password`. Used for setup and admin operations only.

### Environment Variables

**Daily usage (PocketLog):**
- `POCKETLOG_URL` — PocketBase instance URL
- `POCKETLOG_EMAIL` — service account email
- `POCKETLOG_PASSWORD` — service account password

**Admin setup (PocketLogAdmin):**
- `POCKETLOG_URL` — same URL
- `POCKETLOG_ADMIN_EMAIL` — superuser email
- `POCKETLOG_ADMIN_PASSWORD` — superuser password

---

## Error Handling & Retry

- **Logging methods** (`log`, `success`, `error`, `fatal`): retry 3 times with 2-second fixed intervals. On final failure, emit `warnings.warn()` and return `None`. Never raise.
- **All other methods**: raise on error. `ValueError` for validation, `RuntimeError` for API failures, `requests.HTTPError` for unexpected HTTP errors.

---

## PocketBase Collections

Same schema as pocketlogR. Created by `PocketLogAdmin.setup()`.

### `pl_flows`
| Field | Type | Required |
|---|---|---|
| `name` | text | yes |
| `description` | text | no |
| `type` | text | yes |
| `schedule` | text | no |
| `owner` | text | yes |
| `metadata` | json | no |
| `depends_on` | relation (self-ref) | no |

### `pl_logs`
| Field | Type | Required |
|---|---|---|
| `flow` | relation | yes |
| `log_type` | text | yes |
| `status` | text | yes |
| `message` | text | no |
| `metadata` | json | no |
| `logged_by` | text | no |
| `logged_from` | json | no |
| `source_file` | text | no |
| `source_repo` | text | no |
| `created` | autodate | auto |

---

## Tests

- Framework: `pytest`
- No HTTP mocking library required — uses `monkeypatch` for method mocking.
- Test files mirror R test structure:
  - `test_connect.py` — constructor validation
  - `test_flows.py` — constants, create_flow validation, get_flows structure
  - `test_log.py` — log validation, retry logic, convenience wrappers, auto-detection
  - `test_deps.py` — cycle detection, dependency validation, poisoning logic
  - `test_query.py` — get_logs validation, filter building, timestamp formatting
  - `test_admin.py` — delete_flow/delete_logs validation
- All unit tests run without a live PocketBase instance.

### Running tests

```bash
pip install -e ".[dev]"
pytest
```

---

## Coding Standards

- Python 3.10+ type hints with `from __future__ import annotations`.
- All public methods have docstrings with Parameters/Returns sections.
- Internal modules prefixed with underscore (`_base.py`, `_utils.py`).
- `requests.Session` used for connection pooling and persistent auth headers.
- JSON serialization via stdlib `json` module.
- Auto-detection uses `getpass`, `platform`, `inspect`, and `subprocess`.
