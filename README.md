# pocketlogpy

> Log application events to PocketBase from Python

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

`pocketlogpy` is a Python package for unified operational monitoring. It logs events from data pipelines, website checks, email confirmations, and database freshness checks to a [PocketBase](https://pocketbase.io) instance hosted on [PocketHost](https://pockethost.io).

**Use cases:**

- Data job / ETL pipeline logging
- Website uptime monitoring
- Data freshness validation
- Email receipt confirmation
- Website update status tracking

The package writes to two PocketBase collections — `pl_flows` (a registry of your monitored processes) and `pl_logs` (log entries). Flows can declare upstream dependencies, forming a DAG that lets you see cascading failures at a glance.

---

## Admin Setup Guide

This section is for the PocketBase administrator who sets up the instance. End users only need [User Setup](#user-setup-guide).

### Step 1 — Create a PocketHost instance

1. Go to [pockethost.io](https://pockethost.io), create an account, and create a new instance.
2. Note the instance URL — it will look like `https://myapp.pockethost.io`.
3. Access the admin dashboard at `https://myapp.pockethost.io/_/`.

### Step 2 — Create a service account

Create a dedicated service account in the PocketBase dashboard under **Collections → users**.

### Step 3 — Run initial setup from Python

```python
from pocketlogpy import pl_connect_admin, pl_setup

conn_admin = pl_connect_admin(
    url="https://myapp.pockethost.io",
    email="admin@yourorg.com",
    password="your-superuser-password",
)

pl_setup(conn_admin)
```

`pl_setup()` is idempotent — safe to run multiple times.

---

## User Setup Guide

Set three environment variables so pocketlogpy can connect without hardcoding credentials.

| Variable             | Description              | Example                             |
|----------------------|--------------------------|-------------------------------------|
| `POCKETLOG_URL`      | PocketBase instance URL  | `https://myapp.pockethost.io`       |
| `POCKETLOG_EMAIL`    | Service account email    | `pocketlog-service@yourorg.com`     |
| `POCKETLOG_PASSWORD` | Service account password | `your-password`                     |

### Linux / macOS

```bash
export POCKETLOG_URL="https://myapp.pockethost.io"
export POCKETLOG_EMAIL="pocketlog-service@yourorg.com"
export POCKETLOG_PASSWORD="your-password"
```

Or add them to a `.env` file and load with [`python-dotenv`](https://pypi.org/project/python-dotenv/):

```python
from dotenv import load_dotenv
load_dotenv()
```

### Windows (PowerShell)

```powershell
$env:POCKETLOG_URL = "https://myapp.pockethost.io"
$env:POCKETLOG_EMAIL = "pocketlog-service@yourorg.com"
$env:POCKETLOG_PASSWORD = "your-password"
```

---

## Installation

```bash
pip install git+https://github.com/euctrl-pru/pocketlogpy.git
```

---

## Quick Start

```python
from pocketlogpy import (
    pl_connect,
    pl_create_flow,
    pl_success,
    pl_error,
    pl_get_status,
    pl_get_logs,
)

# Connect — reads POCKETLOG_URL, POCKETLOG_EMAIL, POCKETLOG_PASSWORD from env
conn = pl_connect()

# Register your flows once
pl_create_flow(conn, "ectrl_data_load", type="data_job",
               owner="team-data",
               description="Daily EUROCONTROL data import",
               schedule="0 6 * * *")

pl_create_flow(conn, "data_services_email", type="email_check",
               owner="team-data",
               description="Check data services confirmation email received")

# This flow depends on both the data load AND the email confirmation
pl_create_flow(conn, "ans_data_freshness", type="db_check",
               owner="team-data",
               description="Verify ansperformance.eu datasets are current",
               depends_on=["ectrl_data_load", "data_services_email"])

pl_create_flow(conn, "ans_website_online", type="website_online",
               owner="team-ops",
               description="Check ansperformance.eu is reachable")

pl_create_flow(conn, "ans_monthly_update", type="website_status",
               owner="team-data",
               description="Check ansperformance.eu monthly update",
               schedule="0 8 1 * *",
               depends_on=["ans_data_freshness", "ans_website_online"])

# Log outcomes from your scripts (log_type is required)
pl_success(conn, "ectrl_data_load",
           log_type="data_job",
           message="Loaded 14,230 rows",
           metadata={"rows": 14230, "duration_s": 45.2})

pl_error(conn, "ans_website_online",
         log_type="website_online",
         message="HTTP 503 returned",
         metadata={"http_status": 503, "response_time_ms": 12040})

# Check the full dependency chain for a downstream flow
for row in pl_get_status(conn, "ans_monthly_update"):
    print(row["flow"], row["type"], row["status"], f"(depth {row['depth']})")

# Query recent errors
for log in pl_get_logs(conn, status="ERROR", limit=20):
    print(log["flow"], log["created"], log["message"])
```

---

## Dependencies & DAG

Flows can declare upstream dependencies at creation time or later, forming a directed acyclic graph (DAG). The package validates and rejects cycles.

```
ectrl_data_load ──┐
                  ├──► ans_data_freshness ──┐
data_services_email ─┘                    ├──► ans_monthly_update
ans_website_online ──────────────────┘
```

Define dependencies at creation:

```python
pl_create_flow(conn, "ans_data_freshness", type="db_check",
               owner="team-data",
               depends_on=["ectrl_data_load", "data_services_email"])
```

Add or remove them later:

```python
pl_add_dependency(conn, "ans_data_freshness", "another_upstream")
pl_remove_dependency(conn, "ans_data_freshness", "another_upstream")
```

`pl_get_status()` walks the full upstream chain and returns the latest log status for each flow:

```python
for row in pl_get_status(conn, "ans_monthly_update"):
    print(row)
# {'flow': 'ans_monthly_update', 'type': 'website_status', 'status': 'SUCCESS', 'depth': 0, ...}
# {'flow': 'ans_data_freshness',  'type': 'db_check',       'status': 'SUCCESS', 'depth': 1, ...}
# {'flow': 'ans_website_online',  'type': 'website_online', 'status': 'ERROR',   'depth': 1, ...}
# {'flow': 'ectrl_data_load',     'type': 'data_job',       'status': 'SUCCESS', 'depth': 2, ...}
# {'flow': 'data_services_email', 'type': 'email_check',    'status': 'SUCCESS', 'depth': 2, ...}
```

`pl_get_dag()` returns the full picture across all flows, including cascade ("poisoned") status:

```python
dag = pl_get_dag(conn)
for row in dag:
    print(row["flow"], row["effective_status"], row["poisoned_by"])
# ectrl_data_load      SUCCESS  []
# data_services_email  SUCCESS  []
# ans_data_freshness   POISONED ['ectrl_data_load']
# ans_website_online   ERROR    []
# ans_monthly_update   POISONED ['ans_data_freshness']
```

---

## Function Reference

### Daily use

| Function                    | Description                                                              |
|-----------------------------|--------------------------------------------------------------------------|
| `pl_connect()`              | Connect as a regular user                                                |
| `pl_create_flow()`          | Register a new flow                                                      |
| `pl_get_flows()`            | List flows, optionally filtered by name or type                          |
| `pl_add_dependency()`       | Add upstream dependencies to an existing flow                            |
| `pl_remove_dependency()`    | Remove upstream dependencies from an existing flow                       |
| `pl_get_dependencies()`     | List direct or transitive upstream dependencies                          |
| `pl_get_status()`           | Full dependency chain health for a single flow                           |
| `pl_get_dag()`              | Full DAG overview with raw and cascade-aware effective status            |
| `pl_log()`                  | Log an event (`SUCCESS`, `ERROR`, or `FATAL`) with a required `log_type` |
| `pl_success()`              | Shorthand for `pl_log(..., status="SUCCESS")`                            |
| `pl_error()`                | Shorthand for `pl_log(..., status="ERROR")`                              |
| `pl_fatal()`                | Shorthand for `pl_log(..., status="FATAL")`                              |
| `pl_get_logs()`             | Query log entries with optional filters                                  |
| `FLOW_TYPES`                | Tuple of the five default flow type strings                              |
| `LOG_TYPES`                 | Tuple of the five default log type strings                               |

### Admin only

| Function                    | Description                                                              |
|-----------------------------|--------------------------------------------------------------------------|
| `pl_connect_admin()`        | Connect as a superuser                                                   |
| `pl_setup()`                | Create collections and API rules (one-time, idempotent)                  |
| `pl_delete_flow()`          | Delete a flow by name, optionally force-deleting its logs first          |
| `pl_delete_logs()`          | Delete log entries, optionally filtered by flow, status, or date         |

---

## Flow Types

The `type` field on a flow describes what kind of process it is. Five built-in values for consistency — any string accepted.

| Type             | Description                                                    |
|------------------|----------------------------------------------------------------|
| `data_job`       | Data load / ETL process                                        |
| `website_status` | Periodic check whether a website has had its expected update   |
| `email_check`    | Check whether an expected email was received                   |
| `db_check`       | Database freshness check                                       |
| `website_online` | Uptime check — is the website responding?                      |

```python
from pocketlogpy import FLOW_TYPES
print(FLOW_TYPES)
# ('data_job', 'website_status', 'email_check', 'db_check', 'website_online')
```

## Log Types

Every log entry carries a `log_type` — a required field separate from the flow's `type`.

```python
from pocketlogpy import LOG_TYPES
print(LOG_TYPES)
# ('data_job', 'website_online', 'website_status', 'email_check', 'db_check')
```

---

## Admin Operations

### Deleting a flow

```python
conn_admin = pl_connect_admin()

# Safe delete — removes logs then the flow
pl_delete_flow(conn_admin, "old_flow", force=True)

# Without force — errors if logs exist
pl_delete_flow(conn_admin, "empty_flow")
```

### Pruning log entries

```python
conn_admin = pl_connect_admin()
from datetime import datetime, timedelta, timezone

# Delete logs older than 90 days
pl_delete_logs(conn_admin,
               before=datetime.now(timezone.utc) - timedelta(days=90))

# Delete all error logs for a specific flow
pl_delete_logs(conn_admin, flow="ectrl_data_load", status="ERROR")

# Delete all logs for a flow (e.g. before removing it)
pl_delete_logs(conn_admin, flow="old_flow")

# Delete everything (use with care)
pl_delete_logs(conn_admin)
```

---

## Running Tests

```bash
pip install -e ".[dev]"
pytest
```

Unit tests run fully offline. To also run integration tests against a live PocketBase instance, set these environment variables before running:

| Variable                   | Description                         |
|----------------------------|-------------------------------------|
| `POCKETLOG_URL`            | PocketBase instance URL             |
| `POCKETLOG_EMAIL`          | Service account email               |
| `POCKETLOG_PASSWORD`       | Service account password            |
| `POCKETLOG_ADMIN_EMAIL`    | Superuser email (for setup tests)   |
| `POCKETLOG_ADMIN_PASSWORD` | Superuser password (for setup tests)|

Integration tests are skipped automatically when `POCKETLOG_URL` is absent.
