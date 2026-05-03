"""Tests for pl_get_logs."""
import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from pocketlogpy import pl_get_logs
from tests.helpers import make_mock_response


LOG_ITEMS = [{
    "id": "log001",
    "flow": "abc123",
    "log_type": "data_job",
    "status": "SUCCESS",
    "message": "Done",
    "metadata": None,
    "created": "2024-01-01 06:01:00.000",
    "expand": {"flow": {"name": "ectrl_data_load"}},
}]


class TestPlGetLogs:
    def test_returns_list(self, conn):
        resp = make_mock_response(200, {"items": LOG_ITEMS})
        with patch("requests.get", return_value=resp):
            result = pl_get_logs(conn)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["flow"] == "ectrl_data_load"

    def test_returns_empty_list(self, conn):
        resp = make_mock_response(200, {"items": []})
        with patch("requests.get", return_value=resp):
            result = pl_get_logs(conn)
        assert result == []

    def test_filter_by_status(self, conn):
        resp = make_mock_response(200, {"items": []})
        with patch("requests.get", return_value=resp) as mock_get:
            pl_get_logs(conn, status="ERROR")
        params = mock_get.call_args[1]["params"]
        assert "ERROR" in params.get("filter", "")

    def test_filter_by_flow(self, conn):
        resp = make_mock_response(200, {"items": []})
        with patch("requests.get", return_value=resp) as mock_get:
            pl_get_logs(conn, flow="ectrl_data_load")
        params = mock_get.call_args[1]["params"]
        assert "ectrl_data_load" in params.get("filter", "")

    def test_invalid_status_raises(self, conn):
        with pytest.raises(ValueError, match="status"):
            pl_get_logs(conn, status="INVALID")

    def test_limit_sets_perpage(self, conn):
        resp = make_mock_response(200, {"items": []})
        with patch("requests.get", return_value=resp) as mock_get:
            pl_get_logs(conn, limit=10)
        params = mock_get.call_args[1]["params"]
        assert params["perPage"] == 10

    def test_from_filter(self, conn):
        resp = make_mock_response(200, {"items": []})
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        with patch("requests.get", return_value=resp) as mock_get:
            pl_get_logs(conn, from_=ts)
        params = mock_get.call_args[1]["params"]
        assert "2024-01-01" in params.get("filter", "")
