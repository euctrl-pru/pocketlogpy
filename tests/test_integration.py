from __future__ import annotations

# Integration tests — skipped automatically when env vars are absent.
# Set POCKETLOG_URL, POCKETLOG_EMAIL, POCKETLOG_PASSWORD (and POCKETLOG_ADMIN_*
# for admin tests) in your environment to enable.

import os
import time
from datetime import datetime, timedelta

import pytest

from pocketlogpy import PocketLog, PocketLogAdmin
from pocketlogpy.models import DagEntry, Dependency, LogEntry, StatusEntry


def live_conn() -> PocketLog:
    url = os.getenv("POCKETLOG_URL", "")
    email = os.getenv("POCKETLOG_EMAIL", "")
    password = os.getenv("POCKETLOG_PASSWORD", "")
    if not url or not email or not password:
        pytest.skip("Set POCKETLOG_URL, POCKETLOG_EMAIL, POCKETLOG_PASSWORD to run live tests")
    return PocketLog(url=url, email=email, password=password)


def live_admin_conn() -> PocketLogAdmin:
    url = os.getenv("POCKETLOG_URL", "")
    email = os.getenv("POCKETLOG_ADMIN_EMAIL", "")
    password = os.getenv("POCKETLOG_ADMIN_PASSWORD", "")
    if not url or not email or not password:
        pytest.skip("Set POCKETLOG_URL, POCKETLOG_ADMIN_EMAIL, POCKETLOG_ADMIN_PASSWORD to run admin tests")
    return PocketLogAdmin(url=url, email=email, password=password)


def delete_flow(admin: PocketLogAdmin, conn: PocketLog, name: str) -> None:
    try:
        if conn.get_flows(name=name):
            admin.delete_flow(name, force=True)
    except Exception:
        pass


# ── Authentication ─────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_connect_authenticates_against_live_pocketbase():
    conn = live_conn()
    assert isinstance(conn, PocketLog)
    assert conn.url
    assert len(conn.token) > 10


@pytest.mark.integration
def test_connect_admin_authenticates_as_superuser():
    conn = live_admin_conn()
    assert isinstance(conn, PocketLogAdmin)
    assert len(conn.token) > 10


# ── setup ──────────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_setup_is_idempotent():
    admin = live_admin_conn()
    admin.setup()
    admin.setup()


# ── create_flow / get_flows ────────────────────────────────────────────────────

@pytest.mark.integration
def test_create_flow_creates_and_get_flows_retrieves():
    admin = live_admin_conn()
    conn = live_conn()
    nm = f"inttest_create_{datetime.now().strftime('%H%M%S')}"
    try:
        conn.create_flow(nm, type="data_job", owner="test-owner",
                         description="Integration test",
                         schedule="0 6 * * *")
        flows = conn.get_flows(name=nm)
        assert len(flows) == 1
        assert flows[0].name == nm
        assert flows[0].type == "data_job"
        assert flows[0].owner == "test-owner"
        assert flows[0].schedule == "0 6 * * *"
    finally:
        delete_flow(admin, conn, nm)


@pytest.mark.integration
def test_create_flow_stores_and_retrieves_owner():
    admin = live_admin_conn()
    conn = live_conn()
    nm = f"inttest_owner_{datetime.now().strftime('%H%M%S')}"
    try:
        conn.create_flow(nm, type="data_job", owner="team-data")
        flows = conn.get_flows(name=nm)
        assert flows[0].owner == "team-data"
    finally:
        delete_flow(admin, conn, nm)


@pytest.mark.integration
def test_create_flow_errors_if_already_exists():
    admin = live_admin_conn()
    conn = live_conn()
    nm = f"inttest_dup_{datetime.now().strftime('%H%M%S')}"
    try:
        conn.create_flow(nm, type="data_job", owner="test-owner")
        with pytest.raises(Exception, match="already exists"):
            conn.create_flow(nm, type="data_job", owner="test-owner")
    finally:
        delete_flow(admin, conn, nm)


@pytest.mark.integration
def test_get_flows_filters_by_type():
    admin = live_admin_conn()
    conn = live_conn()
    nm = f"inttest_type_{datetime.now().strftime('%H%M%S')}"
    try:
        conn.create_flow(nm, type="website_online", owner="test-owner")
        results = conn.get_flows(type="website_online")
        names = [f.name for f in results]
        assert nm in names
        assert all(f.type == "website_online" for f in results)
    finally:
        delete_flow(admin, conn, nm)


# ── log / success / error / fatal / get_logs ──────────────────────────────────

@pytest.mark.integration
def test_success_logs_entry_and_get_logs_retrieves():
    admin = live_admin_conn()
    conn = live_conn()
    nm = f"inttest_log_{datetime.now().strftime('%H%M%S')}"
    try:
        conn.create_flow(nm, type="data_job", owner="test-owner")
        conn.success(nm, log_type="data_job", message="all good", metadata={"rows": 42})
        logs = conn.get_logs(flow=nm)
        assert len(logs) == 1
        assert isinstance(logs[0], LogEntry)
        assert logs[0].log_type == "data_job"
        assert logs[0].status == "SUCCESS"
        assert logs[0].message == "all good"
        assert hasattr(logs[0], "logged_by")
        assert hasattr(logs[0], "source_file")
        assert hasattr(logs[0], "source_repo")
    finally:
        delete_flow(admin, conn, nm)


@pytest.mark.integration
def test_log_stores_explicit_logged_by_source_file_source_repo():
    admin = live_admin_conn()
    conn = live_conn()
    nm = f"inttest_src_{datetime.now().strftime('%H%M%S')}"
    try:
        conn.create_flow(nm, type="data_job", owner="test-owner")
        conn.success(nm, log_type="data_job", message="with source info",
                     logged_by="test-user", source_file="my_script.py",
                     source_repo="my-repo")
        logs = conn.get_logs(flow=nm)
        assert len(logs) == 1
        assert logs[0].logged_by == "test-user"
        assert logs[0].source_file == "my_script.py"
        assert logs[0].source_repo == "my-repo"
    finally:
        delete_flow(admin, conn, nm)


@pytest.mark.integration
def test_error_and_fatal_log_correct_statuses():
    admin = live_admin_conn()
    conn = live_conn()
    nm = f"inttest_ef_{datetime.now().strftime('%H%M%S')}"
    try:
        conn.create_flow(nm, type="data_job", owner="test-owner")
        conn.error(nm, log_type="data_job", message="something broke")
        conn.fatal(nm, log_type="data_job", message="unrecoverable")
        logs = conn.get_logs(flow=nm)
        assert len(logs) == 2
        statuses = {log.status for log in logs}
        assert statuses == {"ERROR", "FATAL"}
    finally:
        delete_flow(admin, conn, nm)


@pytest.mark.integration
def test_get_logs_filters_by_status():
    admin = live_admin_conn()
    conn = live_conn()
    nm = f"inttest_filt_{datetime.now().strftime('%H%M%S')}"
    try:
        conn.create_flow(nm, type="data_job", owner="test-owner")
        conn.success(nm, log_type="data_job", message="ok")
        conn.error(nm, log_type="data_job", message="bad")

        success_logs = conn.get_logs(flow=nm, status="SUCCESS")
        assert len(success_logs) == 1
        assert success_logs[0].status == "SUCCESS"

        error_logs = conn.get_logs(flow=nm, status="ERROR")
        assert len(error_logs) == 1
        assert error_logs[0].status == "ERROR"
    finally:
        delete_flow(admin, conn, nm)


# ── add_dependency / remove_dependency / get_dependencies ────────────────────

@pytest.mark.integration
def test_add_dependency_and_get_dependencies():
    admin = live_admin_conn()
    conn = live_conn()
    ts = datetime.now().strftime("%H%M%S")
    up = f"inttest_up_{ts}"
    down = f"inttest_down_{ts}"
    try:
        conn.create_flow(up, type="data_job", owner="test-owner")
        conn.create_flow(down, type="db_check", owner="test-owner")
        conn.add_dependency(down, [up])
        deps = conn.get_dependencies(down)
        assert len(deps) == 1
        assert isinstance(deps[0], Dependency)
        assert deps[0].name == up
        assert deps[0].depth == 1
    finally:
        delete_flow(admin, conn, down)
        delete_flow(admin, conn, up)


@pytest.mark.integration
def test_remove_dependency_removes_it():
    admin = live_admin_conn()
    conn = live_conn()
    ts = datetime.now().strftime("%H%M%S")
    up = f"inttest_rup_{ts}"
    down = f"inttest_rdown_{ts}"
    try:
        conn.create_flow(up, type="data_job", owner="test-owner")
        conn.create_flow(down, type="db_check", owner="test-owner", depends_on=[up])
        conn.remove_dependency(down, [up])
        deps = conn.get_dependencies(down)
        assert len(deps) == 0
    finally:
        delete_flow(admin, conn, down)
        delete_flow(admin, conn, up)


@pytest.mark.integration
def test_add_dependency_rejects_cycle():
    admin = live_admin_conn()
    conn = live_conn()
    ts = datetime.now().strftime("%H%M%S")
    a = f"inttest_ca_{ts}"
    b = f"inttest_cb_{ts}"
    try:
        conn.create_flow(a, type="data_job", owner="test-owner")
        conn.create_flow(b, type="data_job", owner="test-owner", depends_on=[a])
        with pytest.raises(ValueError, match="cycle"):
            conn.add_dependency(a, [b])
    finally:
        delete_flow(admin, conn, b)
        delete_flow(admin, conn, a)


@pytest.mark.integration
def test_get_dependencies_recursive_returns_transitive_deps():
    admin = live_admin_conn()
    conn = live_conn()
    ts = datetime.now().strftime("%H%M%S")
    a = f"inttest_ra_{ts}"
    b = f"inttest_rb_{ts}"
    c = f"inttest_rc_{ts}"
    try:
        conn.create_flow(a, type="data_job", owner="test-owner")
        conn.create_flow(b, type="data_job", owner="test-owner", depends_on=[a])
        conn.create_flow(c, type="data_job", owner="test-owner", depends_on=[b])

        deps_direct = conn.get_dependencies(c, recursive=False)
        deps_recursive = conn.get_dependencies(c, recursive=True)

        assert len(deps_direct) == 1
        assert deps_direct[0].name == b

        assert len(deps_recursive) == 2
        assert {d.name for d in deps_recursive} == {a, b}
    finally:
        delete_flow(admin, conn, c)
        delete_flow(admin, conn, b)
        delete_flow(admin, conn, a)


# ── get_status ────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_get_status_returns_chain_with_correct_depths():
    admin = live_admin_conn()
    conn = live_conn()
    ts = datetime.now().strftime("%H%M%S")
    up = f"inttest_sup_{ts}"
    down = f"inttest_sdown_{ts}"
    try:
        conn.create_flow(up, type="data_job", owner="test-owner")
        conn.create_flow(down, type="db_check", owner="test-owner", depends_on=[up])
        conn.success(up, log_type="data_job", message="upstream ok")
        conn.success(down, log_type="db_check", message="downstream ok")

        status = conn.get_status(down)
        assert all(isinstance(s, StatusEntry) for s in status)
        names = [s.flow for s in status]
        assert down in names
        assert up in names

        down_entry = next(s for s in status if s.flow == down)
        up_entry = next(s for s in status if s.flow == up)
        assert down_entry.depth == 0
        assert up_entry.depth == 1
        assert down_entry.status == "SUCCESS"
        assert up_entry.status == "SUCCESS"
    finally:
        delete_flow(admin, conn, down)
        delete_flow(admin, conn, up)


# ── get_dag ────────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_get_dag_returns_correct_structure_and_poisoning():
    admin = live_admin_conn()
    conn = live_conn()
    ts = datetime.now().strftime("%H%M%S")
    up = f"inttest_dup_{ts}"
    down = f"inttest_ddown_{ts}"
    try:
        conn.create_flow(up, type="data_job", owner="test-owner")
        conn.create_flow(down, type="db_check", owner="test-owner", depends_on=[up])

        # Upstream fails, then downstream runs with success → downstream is POISONED
        conn.error(up, log_type="data_job", message="upstream broke")
        time.sleep(1)
        conn.success(down, log_type="db_check", message="downstream ran after upstream broke")

        dag = conn.get_dag()
        assert all(isinstance(e, DagEntry) for e in dag)

        up_entry = next(e for e in dag if e.flow == up)
        down_entry = next(e for e in dag if e.flow == down)

        assert up_entry.raw_status == "ERROR"
        assert up_entry.effective_status == "ERROR"
        assert up_entry.is_root is True

        assert down_entry.raw_status == "SUCCESS"
        assert down_entry.effective_status == "POISONED"
        assert up in down_entry.poisoned_by
        assert down_entry.is_root is False
    finally:
        delete_flow(admin, conn, down)
        delete_flow(admin, conn, up)


@pytest.mark.integration
def test_get_dag_returns_correct_columns_and_types():
    conn = live_conn()
    dag = conn.get_dag()
    assert all(isinstance(e, DagEntry) for e in dag)
    if dag:
        entry = dag[0]
        assert isinstance(entry.flow, str)
        assert isinstance(entry.is_root, bool)
        assert hasattr(entry, "type")
        assert hasattr(entry, "schedule")
        assert hasattr(entry, "raw_status")
        assert hasattr(entry, "raw_status_time")
        assert hasattr(entry, "effective_status")
        assert hasattr(entry, "poisoned_by")
        assert hasattr(entry, "depends_on")


# ── delete_flow ────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_delete_flow_errors_on_unknown_flow():
    admin = live_admin_conn()
    with pytest.raises(ValueError, match="not found"):
        admin.delete_flow("nonexistent_flow_xyz")


@pytest.mark.integration
def test_delete_flow_removes_flow_with_no_logs():
    admin = live_admin_conn()
    conn = live_conn()
    nm = f"admin_del_{datetime.now().strftime('%H%M%S')}"
    conn.create_flow(nm, type="data_job", owner="test-owner")
    assert len(conn.get_flows(name=nm)) == 1
    admin.delete_flow(nm)
    assert len(conn.get_flows(name=nm)) == 0


@pytest.mark.integration
def test_delete_flow_errors_when_logs_exist_and_force_false():
    admin = live_admin_conn()
    conn = live_conn()
    nm = f"admin_noforce_{datetime.now().strftime('%H%M%S')}"
    try:
        conn.create_flow(nm, type="data_job", owner="test-owner")
        conn.success(nm, log_type="data_job", message="test log")
        with pytest.raises(RuntimeError, match="log entries"):
            admin.delete_flow(nm, force=False)
    finally:
        admin.delete_flow(nm, force=True)


@pytest.mark.integration
def test_delete_flow_force_removes_logs_then_flow():
    admin = live_admin_conn()
    conn = live_conn()
    nm = f"admin_force_{datetime.now().strftime('%H%M%S')}"
    conn.create_flow(nm, type="data_job", owner="test-owner")
    conn.success(nm, log_type="data_job", message="will be deleted")
    conn.error(nm, log_type="data_job", message="this too")
    admin.delete_flow(nm, force=True)
    assert len(conn.get_flows(name=nm)) == 0
    assert len(conn.get_logs(flow=nm)) == 0


# ── delete_logs ────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_delete_logs_removes_logs_matching_flow_filter():
    admin = live_admin_conn()
    conn = live_conn()
    nm = f"admin_dlog_{datetime.now().strftime('%H%M%S')}"
    try:
        conn.create_flow(nm, type="data_job", owner="test-owner")
        conn.success(nm, log_type="data_job", message="a")
        conn.error(nm, log_type="data_job", message="b")
        assert len(conn.get_logs(flow=nm)) == 2
        n = admin.delete_logs(flow=nm)
        assert n == 2
        assert len(conn.get_logs(flow=nm)) == 0
    finally:
        delete_flow(admin, conn, nm)


@pytest.mark.integration
def test_delete_logs_respects_status_filter():
    admin = live_admin_conn()
    conn = live_conn()
    nm = f"admin_dstat_{datetime.now().strftime('%H%M%S')}"
    try:
        conn.create_flow(nm, type="data_job", owner="test-owner")
        conn.success(nm, log_type="data_job", message="keep me")
        conn.error(nm, log_type="data_job", message="delete me")
        n = admin.delete_logs(flow=nm, status="ERROR")
        assert n == 1
        remaining = conn.get_logs(flow=nm)
        assert len(remaining) == 1
        assert remaining[0].status == "SUCCESS"
    finally:
        delete_flow(admin, conn, nm)


@pytest.mark.integration
def test_delete_logs_respects_before_filter():
    admin = live_admin_conn()
    conn = live_conn()
    nm = f"admin_dbef_{datetime.now().strftime('%H%M%S')}"
    try:
        conn.create_flow(nm, type="data_job", owner="test-owner")
        conn.success(nm, log_type="data_job", message="old log")
        n = admin.delete_logs(flow=nm, before=datetime.now() + timedelta(hours=1))
        assert n == 1
        assert len(conn.get_logs(flow=nm)) == 0
    finally:
        delete_flow(admin, conn, nm)


@pytest.mark.integration
def test_delete_logs_returns_zero_when_nothing_matches():
    admin = live_admin_conn()
    conn = live_conn()
    nm = f"admin_dnone_{datetime.now().strftime('%H%M%S')}"
    try:
        conn.create_flow(nm, type="data_job", owner="test-owner")
        n = admin.delete_logs(flow=nm)
        assert n == 0
    finally:
        delete_flow(admin, conn, nm)
