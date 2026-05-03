"""Integration tests against a live PocketBase instance.

Skipped automatically when POCKETLOG_URL is not set. Set these environment
variables to run them::

    POCKETLOG_URL             PocketBase instance URL
    POCKETLOG_EMAIL           Service account email
    POCKETLOG_PASSWORD        Service account password
    POCKETLOG_ADMIN_EMAIL     Superuser email
    POCKETLOG_ADMIN_PASSWORD  Superuser password
"""
import os
import uuid
import pytest


INTEGRATION = pytest.mark.skipif(
    not os.environ.get("POCKETLOG_URL"),
    reason="Integration tests require POCKETLOG_URL to be set",
)


@pytest.fixture(scope="module")
def conn():
    from pocketlogpy import pl_connect
    return pl_connect()


@pytest.fixture(scope="module")
def admin_conn():
    from pocketlogpy import pl_connect_admin
    return pl_connect_admin()


@pytest.fixture(scope="module")
def flow_name():
    return f"test_flow_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def upstream_name():
    return f"test_upstream_{uuid.uuid4().hex[:8]}"


@INTEGRATION
class TestIntegration:
    def test_setup_is_idempotent(self, admin_conn):
        from pocketlogpy import pl_setup
        pl_setup(admin_conn)
        pl_setup(admin_conn)

    def test_create_and_get_flow(self, conn, flow_name):
        from pocketlogpy import pl_create_flow, pl_get_flows
        pl_create_flow(conn, flow_name, type="data_job", owner="test")
        flows = pl_get_flows(conn, name=flow_name)
        assert len(flows) == 1
        assert flows[0]["name"] == flow_name

    def test_log_success(self, conn, flow_name):
        from pocketlogpy import pl_success
        result = pl_success(conn, flow_name, log_type="data_job",
                            message="Integration test")
        assert result is not None
        assert result["status"] == "SUCCESS"

    def test_log_error(self, conn, flow_name):
        from pocketlogpy import pl_error
        result = pl_error(conn, flow_name, log_type="data_job",
                          message="Test error")
        assert result is not None
        assert result["status"] == "ERROR"

    def test_get_logs(self, conn, flow_name):
        from pocketlogpy import pl_get_logs
        logs = pl_get_logs(conn, flow=flow_name)
        assert len(logs) >= 1

    def test_get_status(self, conn, flow_name):
        from pocketlogpy import pl_get_status
        status = pl_get_status(conn, flow_name)
        assert any(r["flow"] == flow_name for r in status)

    def test_get_dag(self, conn):
        from pocketlogpy import pl_get_dag
        dag = pl_get_dag(conn)
        assert isinstance(dag, list)

    def test_add_and_remove_dependency(self, conn, upstream_name, flow_name):
        from pocketlogpy import pl_create_flow, pl_get_flows
        from pocketlogpy import pl_add_dependency, pl_remove_dependency
        pl_create_flow(conn, upstream_name, type="data_job", owner="test")

        pl_add_dependency(conn, flow_name, upstream_name)
        flows = pl_get_flows(conn, name=flow_name)
        assert upstream_name in flows[0]["depends_on"]

        pl_remove_dependency(conn, flow_name, upstream_name)
        flows = pl_get_flows(conn, name=flow_name)
        assert upstream_name not in flows[0]["depends_on"]

    def test_cleanup(self, admin_conn, conn, flow_name, upstream_name):
        from pocketlogpy import pl_delete_flow, pl_get_flows
        pl_delete_flow(admin_conn, flow_name, force=True)
        pl_delete_flow(admin_conn, upstream_name, force=True)
        assert pl_get_flows(conn, name=flow_name) == []
        assert pl_get_flows(conn, name=upstream_name) == []
