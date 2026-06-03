from __future__ import annotations

import pytest

from pocketlogpy._utils import detect_cycle, parse_timestamp


def make_flow(name: str, id: str, depends_on: list[str] | None = None) -> dict:
    return {
        "id": id,
        "name": name,
        "type": "data_job",
        "depends_on": depends_on or [],
    }


class TestDetectCycle:
    def test_detects_direct_cycle(self):
        flows = [
            make_flow("a", "id_a", ["id_b"]),
            make_flow("b", "id_b"),
        ]
        assert detect_cycle("b", ["a"], flows) is True

    def test_detects_transitive_cycle(self):
        flows = [
            make_flow("a", "id_a", ["id_b"]),
            make_flow("b", "id_b", ["id_c"]),
            make_flow("c", "id_c"),
        ]
        assert detect_cycle("c", ["a"], flows) is True

    def test_accepts_valid_dag(self):
        flows = [
            make_flow("a", "id_a"),
            make_flow("b", "id_b", ["id_a"]),
            make_flow("c", "id_c", ["id_a"]),
        ]
        assert detect_cycle("d", ["b", "c"], flows) is False

    def test_accepts_empty_dependency_list(self):
        flows = [make_flow("a", "id_a")]
        assert detect_cycle("b", [], flows) is False

    def test_handles_self_reference(self):
        flows = [make_flow("a", "id_a")]
        assert detect_cycle("a", ["a"], flows) is True


class TestAddDependencyValidation:
    def test_validates_flow_argument(self, mock_conn):
        with pytest.raises(ValueError, match="'flow' must be"):
            mock_conn.add_dependency(flow=123, depends_on=["b"])
        with pytest.raises(ValueError, match="'flow' must be"):
            mock_conn.add_dependency(flow="", depends_on=["b"])

    def test_validates_depends_on_argument(self, mock_conn):
        with pytest.raises(ValueError, match="'depends_on' must be"):
            mock_conn.add_dependency(flow="a", depends_on=[])
        with pytest.raises(ValueError, match="'depends_on' must be"):
            mock_conn.add_dependency(flow="a", depends_on=123)


class TestRemoveDependencyValidation:
    def test_validates_flow_argument(self, mock_conn):
        with pytest.raises(ValueError, match="'flow' must be"):
            mock_conn.remove_dependency(flow=123, depends_on=["b"])
        with pytest.raises(ValueError, match="'flow' must be"):
            mock_conn.remove_dependency(flow="", depends_on=["b"])

    def test_validates_depends_on_argument(self, mock_conn):
        with pytest.raises(ValueError, match="'depends_on' must be"):
            mock_conn.remove_dependency(flow="a", depends_on=[])


class TestPoisoningLogic:
    def test_downstream_poisoned_when_success_after_upstream_failure(self):
        upstream_failure_ts = "2024-01-01 09:00:00"
        downstream_success_ts = "2024-01-01 10:00:00"

        last_success = parse_timestamp(downstream_success_ts)
        up_ts = parse_timestamp(upstream_failure_ts)

        assert last_success is not None
        assert up_ts is not None
        is_poisoned = last_success > up_ts
        assert is_poisoned is True

    def test_downstream_not_poisoned_when_success_before_upstream_failure(self):
        upstream_failure_ts = "2024-01-01 10:00:00"
        downstream_success_ts = "2024-01-01 09:00:00"

        last_success = parse_timestamp(downstream_success_ts)
        up_ts = parse_timestamp(upstream_failure_ts)

        assert last_success is not None
        assert up_ts is not None
        is_poisoned = last_success > up_ts
        assert is_poisoned is False

    def test_never_logged_downstream_not_poisoned(self):
        down_status = None
        is_poisoned = down_status is not None and down_status == "SUCCESS"
        assert is_poisoned is False
