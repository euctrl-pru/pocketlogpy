"""Tests for dependency management and DAG functions."""
import pytest
from unittest.mock import patch

from pocketlogpy import (
    pl_add_dependency,
    pl_remove_dependency,
    pl_get_dependencies,
    pl_get_status,
    pl_get_dag,
)
from tests.helpers import make_mock_response, make_flows_response


FLOW_A = {"id": "id_a", "name": "flow_a", "type": "data_job",
           "description": None, "schedule": None, "depends_on": []}
FLOW_B = {"id": "id_b", "name": "flow_b", "type": "db_check",
           "description": None, "schedule": None, "depends_on": ["id_a"]}
FLOW_C = {"id": "id_c", "name": "flow_c", "type": "website_status",
           "description": None, "schedule": None, "depends_on": ["id_b"]}
ALL_FLOWS = [FLOW_A, FLOW_B, FLOW_C]


def _flows_get(*args, **kwargs):
    return make_flows_response(ALL_FLOWS)


def _logs_empty(*args, **kwargs):
    return make_mock_response(200, {"items": [], "totalPages": 1})


class TestPlGetDependencies:
    def test_direct_deps(self, conn):
        with patch("requests.get", side_effect=_flows_get):
            result = pl_get_dependencies(conn, "flow_b")
        assert len(result) == 1
        assert result[0]["name"] == "flow_a"
        assert result[0]["depth"] == 1

    def test_recursive_deps(self, conn):
        with patch("requests.get", side_effect=_flows_get):
            result = pl_get_dependencies(conn, "flow_c", recursive=True)
        names = [r["name"] for r in result]
        assert "flow_b" in names
        assert "flow_a" in names

    def test_no_deps_returns_empty(self, conn):
        with patch("requests.get", side_effect=_flows_get):
            result = pl_get_dependencies(conn, "flow_a")
        assert result == []

    def test_flow_not_found_raises(self, conn):
        with patch("requests.get", side_effect=_flows_get):
            with pytest.raises(ValueError, match="not found"):
                pl_get_dependencies(conn, "nonexistent")


class TestPlGetStatus:
    def _make_get(self, log_status="SUCCESS"):
        log_item = {
            "status": log_status, "message": "OK",
            "created": "2024-01-01 06:00:00.000",
        }
        log_resp = make_mock_response(
            200, {"items": [log_item], "totalPages": 1}
        )

        def mock_get(*args, **kwargs):
            url = args[0] if args else ""
            return log_resp if "pl_logs" in url else make_flows_response(ALL_FLOWS)
        return mock_get

    def test_returns_full_chain(self, conn):
        with patch("requests.get", side_effect=self._make_get()):
            result = pl_get_status(conn, "flow_c")
        names = [r["flow"] for r in result]
        assert "flow_c" in names
        assert "flow_b" in names
        assert "flow_a" in names

    def test_sorted_by_depth(self, conn):
        with patch("requests.get", side_effect=self._make_get()):
            result = pl_get_status(conn, "flow_c")
        depths = [r["depth"] for r in result]
        assert depths == sorted(depths)

    def test_flow_not_found_raises(self, conn):
        with patch("requests.get", side_effect=_flows_get):
            with pytest.raises(ValueError, match="not found"):
                pl_get_status(conn, "nonexistent")


class TestCycleDetection:
    def test_direct_cycle(self):
        from pocketlogpy._utils import _detect_cycle
        flows = [
            {"id": "id_a", "name": "flow_a", "depends_on": ["id_b"]},
            {"id": "id_b", "name": "flow_b", "depends_on": []},
        ]
        assert _detect_cycle("flow_b", ["flow_a"], flows) is True

    def test_transitive_cycle(self):
        from pocketlogpy._utils import _detect_cycle
        flows = [
            {"id": "id_a", "name": "flow_a", "depends_on": ["id_b"]},
            {"id": "id_b", "name": "flow_b", "depends_on": ["id_c"]},
            {"id": "id_c", "name": "flow_c", "depends_on": []},
        ]
        assert _detect_cycle("flow_c", ["flow_a"], flows) is True

    def test_no_cycle(self):
        from pocketlogpy._utils import _detect_cycle
        flows = [
            {"id": "id_a", "name": "flow_a", "depends_on": []},
            {"id": "id_b", "name": "flow_b", "depends_on": []},
        ]
        assert _detect_cycle("flow_c", ["flow_a", "flow_b"], flows) is False
