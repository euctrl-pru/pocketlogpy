"""Tests for pl_create_flow and pl_get_flows."""
import pytest
from unittest.mock import patch

from pocketlogpy import pl_create_flow, pl_get_flows
from tests.helpers import make_mock_response, make_flows_response


SAMPLE_FLOW = {
    "id": "abc123",
    "name": "ectrl_data_load",
    "type": "data_job",
    "description": "Daily load",
    "schedule": "0 6 * * *",
    "owner": "quinten",
    "metadata": None,
    "depends_on": [],
    "created": "2024-01-01 06:00:00.000",
    "updated": "2024-01-01 06:00:00.000",
}


class TestPlGetFlows:
    def test_returns_list(self, conn):
        with patch("requests.get", return_value=make_flows_response([SAMPLE_FLOW])):
            result = pl_get_flows(conn)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "ectrl_data_load"

    def test_returns_empty_list(self, conn):
        with patch("requests.get", return_value=make_flows_response([])):
            result = pl_get_flows(conn)
        assert result == []

    def test_filter_by_name_passed_in_params(self, conn):
        with patch("requests.get", return_value=make_flows_response([])) as mock_get:
            pl_get_flows(conn, name="ectrl_data_load")
        params = mock_get.call_args[1]["params"]
        assert "ectrl_data_load" in params.get("filter", "")

    def test_filter_by_type_passed_in_params(self, conn):
        with patch("requests.get", return_value=make_flows_response([])) as mock_get:
            pl_get_flows(conn, type="data_job")
        params = mock_get.call_args[1]["params"]
        assert "data_job" in params.get("filter", "")

    def test_depends_on_resolved_to_names(self, conn):
        flow_with_dep = {**SAMPLE_FLOW, "id": "def456",
                         "name": "downstream", "depends_on": ["abc123"]}
        with patch("requests.get",
                   return_value=make_flows_response([SAMPLE_FLOW, flow_with_dep])):
            result = pl_get_flows(conn)
        downstream = next(r for r in result if r["name"] == "downstream")
        assert downstream["depends_on"] == ["ectrl_data_load"]

    def test_invalid_conn_raises(self):
        with pytest.raises(TypeError):
            pl_get_flows({"url": "x", "token": "y"})


class TestPlCreateFlow:
    def test_creates_flow(self, conn):
        with patch("requests.get", return_value=make_flows_response([])), \
             patch("requests.post",
                   return_value=make_mock_response(200, SAMPLE_FLOW)):
            result = pl_create_flow(
                conn, "ectrl_data_load", type="data_job", owner="quinten"
            )
        assert result["name"] == "ectrl_data_load"

    def test_raises_if_flow_exists(self, conn):
        with patch("requests.get",
                   return_value=make_flows_response([SAMPLE_FLOW])):
            with pytest.raises(ValueError, match="already exists"):
                pl_create_flow(
                    conn, "ectrl_data_load", type="data_job", owner="quinten"
                )

    def test_raises_on_empty_name(self, conn):
        with pytest.raises(ValueError, match="name"):
            pl_create_flow(conn, "", type="data_job", owner="quinten")

    def test_raises_on_empty_type(self, conn):
        with pytest.raises(ValueError, match="type"):
            pl_create_flow(conn, "my_flow", type="", owner="quinten")

    def test_raises_on_empty_owner(self, conn):
        with pytest.raises(ValueError, match="owner"):
            pl_create_flow(conn, "my_flow", type="data_job", owner="")
