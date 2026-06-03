from __future__ import annotations

import pytest

from pocketlogpy import FLOW_TYPES, PocketLog
from pocketlogpy.models import Flow


class TestFlowTypes:
    def test_contains_expected_values(self):
        assert "data_job" in FLOW_TYPES
        assert "website_status" in FLOW_TYPES
        assert "email_check" in FLOW_TYPES
        assert "db_check" in FLOW_TYPES
        assert "website_online" in FLOW_TYPES

    def test_is_tuple(self):
        assert isinstance(FLOW_TYPES, tuple)


class TestCreateFlowValidation:
    def test_name_must_be_nonempty_string(self, mock_conn):
        with pytest.raises(ValueError, match="'name' must be"):
            mock_conn.create_flow(name=123, type="data_job", owner="x")
        with pytest.raises(ValueError, match="'name' must be"):
            mock_conn.create_flow(name="", type="data_job", owner="x")

    def test_type_must_be_nonempty_string(self, mock_conn):
        with pytest.raises(ValueError, match="'type' must be"):
            mock_conn.create_flow(name="myflow", type="", owner="x")
        with pytest.raises(ValueError, match="'type' must be"):
            mock_conn.create_flow(name="myflow", type=42, owner="x")

    def test_owner_must_be_nonempty_string(self, mock_conn):
        with pytest.raises(ValueError, match="'owner' must be"):
            mock_conn.create_flow(name="myflow", type="data_job", owner="")
        with pytest.raises(ValueError, match="'owner' must be"):
            mock_conn.create_flow(name="myflow", type="data_job", owner=123)


class TestGetFlows:
    def test_returns_empty_list_when_no_results(self, mock_conn, monkeypatch):
        monkeypatch.setattr(
            mock_conn,
            "_get",
            lambda path, **kw: {"items": [], "totalPages": 1},
        )
        result = mock_conn.get_flows()
        assert result == []

    def test_returns_flow_objects(self, mock_conn, monkeypatch):
        monkeypatch.setattr(
            mock_conn,
            "_get",
            lambda path, **kw: {
                "items": [
                    {
                        "id": "abc123",
                        "name": "myflow",
                        "type": "data_job",
                        "owner": "quinten",
                        "description": "A test flow",
                        "schedule": None,
                        "metadata": None,
                        "depends_on": [],
                        "created": "2024-01-01 00:00:00",
                        "updated": "2024-01-01 00:00:00",
                    }
                ],
                "totalPages": 1,
            },
        )
        result = mock_conn.get_flows()
        assert len(result) == 1
        assert isinstance(result[0], Flow)
        assert result[0].name == "myflow"
        assert result[0].type == "data_job"
        assert result[0].owner == "quinten"

    def test_resolves_depends_on_names(self, mock_conn, monkeypatch):
        monkeypatch.setattr(
            mock_conn,
            "_get",
            lambda path, **kw: {
                "items": [
                    {
                        "id": "id_a",
                        "name": "flow_a",
                        "type": "data_job",
                        "owner": "x",
                        "description": None,
                        "schedule": None,
                        "metadata": None,
                        "depends_on": [],
                        "created": "",
                        "updated": "",
                    },
                    {
                        "id": "id_b",
                        "name": "flow_b",
                        "type": "data_job",
                        "owner": "x",
                        "description": None,
                        "schedule": None,
                        "metadata": None,
                        "depends_on": ["id_a"],
                        "created": "",
                        "updated": "",
                    },
                ],
                "totalPages": 1,
            },
        )
        result = mock_conn.get_flows()
        assert result[1].depends_on == ["flow_a"]
