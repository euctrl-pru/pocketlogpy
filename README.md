# pocketlogpy

Log application events to PocketBase from Python.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## Overview

**pocketlogpy** is a Python package for unified operational monitoring that logs application events to a [PocketBase](https://pocketbase.io) instance hosted on [PocketHost](https://pockethost.io). It is the Python mirror of [pocketlogR](https://github.com/euctrl-pru/pocketlogR), redesigned with a class-oriented API.

Use cases:
- Data job / ETL logging
- Website uptime monitoring
- Data freshness validation
- Email receipt confirmation
- Website update status tracking

The package uses two PocketBase collections (`pl_flows` and `pl_logs`), supports DAG-based flow dependencies with chain health checks, and authenticates as a regular user (not superuser) for daily operations.

## Admin Setup Guide

### Step 1: Create a PocketHost instance

Go to [pockethost.io](https://pockethost.io), create an account and a new instance. Note the URL (e.g. `https://myapp.pockethost.io`).

### Step 2: Create a service account user

In the PocketBase Dashboard (**Collections > users**), create a dedicated user:
- Email: e.g. `pocketlog-service@yourorg.com`
- Password: a strong password

### Step 3: Run initial setup from Python

```python
from pocketlogpy import PocketLogAdmin

admin = PocketLogAdmin(
    url="https://myapp.pockethost.io",
    email="admin@yourorg.com",
    password="your-superuser-password",
)
admin.setup()
```

This creates the `pl_flows` and `pl_logs` collections. After this step, superuser credentials are no longer needed.

### Step 4: Distribute credentials

Share with your team:
- The PocketBase URL
- The service account email and password

## User Setup

Set environment variables:

| Variable | Description | Example |
|---|---|---|
| `POCKETLOG_URL` | PocketBase instance URL | `https://myapp.pockethost.io` |
| `POCKETLOG_EMAIL` | Service account email | `pocketlog-service@yourorg.com` |
| `POCKETLOG_PASSWORD` | Service account password | `your-password` |

**Linux / macOS:**
```bash
export POCKETLOG_URL="https://myapp.pockethost.io"
export POCKETLOG_EMAIL="pocketlog-service@yourorg.com"
export POCKETLOG_PASSWORD="your-password"
```

**Windows (PowerShell):**
```powershell
[System.Environment]::SetEnvironmentVariable("POCKETLOG_URL", "https://myapp.pockethost.io", "User")
[System.Environment]::SetEnvironmentVariable("POCKETLOG_EMAIL", "pocketlog-service@yourorg.com", "User")
[System.Environment]::SetEnvironmentVariable("POCKETLOG_PASSWORD", "your-password", "User")
```

**`.env` file** (with python-dotenv):
```
POCKETLOG_URL=https://myapp.pockethost.io
POCKETLOG_EMAIL=pocketlog-service@yourorg.com
POCKETLOG_PASSWORD=your-password
```

## Virtual Environment Setup

Create and activate a virtual environment before installing:

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

## Installation

```bash
pip install -e ".[dev]"
```

## Running Tests

Install the dev dependencies, then run the test suite with pytest:

```bash
pip install -e ".[dev]"
pytest
```

### Unit Tests

Unit tests run without a live PocketBase instance and cover all functionality via mocked HTTP calls. To run only unit tests explicitly:

```bash
pytest -m "not integration"
```

### Integration Tests

Integration tests (marked with `@pytest.mark.integration`) require a running PocketBase instance and are skipped by default. To run integration tests:

```bash
pytest -m "integration"
```

These tests write real data to your PocketBase instance, so use a dedicated test instance, not production.

## Quick Start

```python
from pocketlogpy import PocketLog

# Connect (reads env vars automatically)
pl = PocketLog()

# Register flows (once)
pl.create_flow("ectrl_data_load", type="data_job", owner="quinten",
               description="Daily EUROCONTROL data import",
               schedule="0 6 * * *")

pl.create_flow("data_services_email", type="email_check", owner="quinten",
               description="Check data services confirmation email received")

# This flow depends on both the data load AND the email confirmation
pl.create_flow("ans_data_freshness", type="db_check", owner="quinten",
               description="Verify ansperformance.eu datasets are current",
               depends_on=["ectrl_data_load", "data_services_email"])

pl.create_flow("ans_website_online", type="website_online", owner="quinten",
               description="Check ansperformance.eu is reachable")

pl.create_flow("ans_monthly_update", type="website_status", owner="quinten",
               description="Check ansperformance.eu monthly update",
               schedule="0 8 1 * *",
               depends_on=["ans_data_freshness", "ans_website_online"])

# Add a dependency to an existing flow later
pl.add_dependency("ans_data_freshness", ["another_upstream_flow"])

# Log outcomes
pl.success("ectrl_data_load", log_type="data_job",
           message="Loaded 14,230 rows",
           metadata={"rows": 14230, "duration_s": 45.2})

pl.error("ans_website_online", log_type="website_online",
         message="HTTP 503 returned",
         metadata={"http_status": 503, "response_time_ms": 12040})

# Check the full dependency chain health
status = pl.get_status("ans_monthly_update")
for entry in status:
    print(f"  {entry.flow} ({entry.type}): {entry.status} [depth={entry.depth}]")

# Query recent errors
errors = pl.get_logs(status="ERROR", limit=20)

# List all website monitoring flows
web_flows = pl.get_flows(type="website_online")
```

## Function Reference

### PocketLog (daily operations)

| Method | Description |
|---|---|
| `PocketLog(url, email, password)` | Connect as regular user |
| `create_flow(name, type, owner, ...)` | Register a new flow |
| `get_flows(type, name)` | List flows with optional filtering |
| `add_dependency(flow, depends_on)` | Add upstream dependencies |
| `remove_dependency(flow, depends_on)` | Remove upstream dependencies |
| `get_dependencies(flow, recursive)` | Get upstream dependency tree |
| `get_status(flow, since)` | Get dependency chain health |
| `get_dag(since)` | Get full DAG overview with effective status |
| `log(flow, status, log_type, ...)` | Record a log entry (with retry) |
| `success(flow, log_type, ...)` | Log a SUCCESS event |
| `error(flow, log_type, ...)` | Log an ERROR event |
| `fatal(flow, log_type, ...)` | Log a FATAL event |
| `get_logs(flow, status, from_, to, limit)` | Query log entries |

### PocketLogAdmin (setup & admin)

| Method | Description |
|---|---|
| `PocketLogAdmin(url, email, password)` | Connect as superuser |
| `setup()` | Create pl_flows and pl_logs collections |
| `delete_flow(flow, force)` | Delete a flow (force removes logs first) |
| `delete_logs(flow, before, status)` | Delete log entries matching filters |

### Return Types

All query methods return typed dataclass instances:

- **`Flow`** — id, name, type, owner, description, schedule, metadata, depends_on, created, updated
- **`LogEntry`** — id, flow, log_type, status, message, metadata, logged_by, logged_from, source_file, source_repo, created
- **`Dependency`** — name, type, description, schedule, depth
- **`StatusEntry`** — flow, type, status, message, created, depth
- **`DagEntry`** — flow, type, schedule, raw_status, raw_status_time, effective_status, poisoned_by, depends_on, is_root

### Constants

- **`FLOW_TYPES`** — `("data_job", "website_status", "email_check", "db_check", "website_online")`
- **`LOG_TYPES`** — `("data_job", "website_online", "website_status", "email_check", "db_check")`
- **`VALID_STATUSES`** — `("SUCCESS", "ERROR", "FATAL")`

## Dependencies & DAG

Flows can declare upstream dependencies via `depends_on`, forming a directed acyclic graph (DAG). Cycles are detected and rejected.

```
ectrl_data_load ─────┐
                     ├──► ans_data_freshness ──┐
data_services_email ─┘                        ├──► ans_monthly_update
                        ans_website_online ────┘
```

- **`get_status(flow)`** walks the chain upward and returns health for each flow.
- **`get_dag()`** returns all flows with effective status, detecting "poisoned" flows (ran after upstream broke).
- Dependencies are purely informational — logging is never blocked.
- Adding a dependency that would create a cycle raises `ValueError`.

## Flow Types

| Type | Description |
|---|---|
| `data_job` | Data load / ETL process |
| `website_status` | Periodic website update check |
| `email_check` | Expected email receipt check |
| `db_check` | Database freshness validation |
| `website_online` | Website uptime check |

These are not enforced — any string is accepted as a type.

## Error Handling

- **Logging methods** (`log`, `success`, `error`, `fatal`): retry 3 times with 2-second intervals. On final failure, emit a `UserWarning` and return `None`. Never raise.
- **All other methods**: raise on error (`ValueError` for validation, `RuntimeError` / `requests.HTTPError` for HTTP failures).
