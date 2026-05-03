"""Tests for pl_delete_flow and pl_delete_logs."""
import pytest
from unittest.mock import patch

from pocketlogpy import pl_delete_flow, pl_delete_logs
from tests.helpers import make_mock_response, make_flows_response


SAMPLE_FLOW = {"id": "abc123", "name": "old_flow",
               "type": "data_job", "depends_on": []}


class TestPlDeleteFlow:
    def test_deletes_flow(self, admin_conn):
        def mock_get(*args, **kwargs):
            return make_flows_response([SAMPLE_FLOW])

        with patch("requests.get", side_effect=mock_get), \
             patch("requests.delete",
                   return_value=make_mock_response(204)):
            pl_delete_flow(admin_conn, "old_flow")

    def test_force_deletes_logs_first(self, admin_conn):
        log_ids_resp = make_mock_response(
            200, {"items": [{"id": "log1"}], "totalPages": 1}
        )

        def mock_get(*args, **kwargs):
            url = args[0] if args else ""
            return log_ids_resp if "pl_logs" in url \
                else make_flows_response([SAMPLE_FLOW])

        delete_calls = []

        def mock_delete(*args, **kwargs):
            delete_calls.append(args[0])
            return make_mock_response(204)

        with patch("requests.get", side_effect=mock_get), \
             patch("requests.delete", side_effect=mock_delete):
            pl_delete_flow(admin_conn, "old_flow", force=True)

        assert len(delete_calls) == 2  # log first, then flow

    def test_raises_on_missing_flow(self, admin_conn):
        with patch("requests.get", return_value=make_flows_response([])):
            with pytest.raises(ValueError, match="not found"):
                pl_delete_flow(admin_conn, "nonexistent")

    def test_raises_on_empty_name(self, admin_conn):
        with pytest.raises(ValueError, match="flow"):
            pl_delete_flow(admin_conn, "")


class TestPlDeleteLogs:
    def test_deletes_matching_logs(self, admin_conn):
        ids_resp = make_mock_response(
            200, {"items": [{"id": "l1"}, {"id": "l2"}], "totalPages": 1}
        )
        with patch("requests.get", return_value=ids_resp), \
             patch("requests.delete", return_value=make_mock_response(204)):
            count = pl_delete_logs(admin_conn, flow="ectrl_data_load")
        assert count == 2

    def test_no_matches_returns_zero(self, admin_conn):
        with patch("requests.get",
                   return_value=make_mock_response(
                       200, {"items": [], "totalPages": 1}
                   )):
            count = pl_delete_logs(admin_conn)
        assert count == 0

    def test_invalid_status_raises(self, admin_conn):
        with pytest.raises(ValueError, match="status"):
            pl_delete_logs(admin_conn, status="INVALID")
