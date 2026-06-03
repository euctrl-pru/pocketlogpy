from __future__ import annotations

import pytest

from pocketlogpy import PocketLogAdmin


class TestDeleteFlowValidation:
    def test_validates_flow_argument(self, mock_admin):
        with pytest.raises(ValueError, match="'flow' must be"):
            mock_admin.delete_flow("")
        with pytest.raises(ValueError, match="'flow' must be"):
            mock_admin.delete_flow(123)

    def test_errors_on_unknown_flow(self, mock_admin, monkeypatch):
        monkeypatch.setattr(
            mock_admin,
            "_get_flows_raw_by_name",
            lambda name: [],
        )
        with pytest.raises(ValueError, match="not found"):
            mock_admin.delete_flow("nonexistent_flow")


class TestDeleteLogsValidation:
    def test_validates_status_argument(self, mock_admin):
        with pytest.raises(ValueError, match="'status' must be one of"):
            mock_admin.delete_logs(status="INVALID")

    def test_returns_zero_when_nothing_matches(self, mock_admin, monkeypatch):
        monkeypatch.setattr(
            mock_admin,
            "_collect_log_ids",
            lambda filt=None: [],
        )
        result = mock_admin.delete_logs(flow="nonexistent")
        assert result == 0

    def test_accepts_valid_statuses(self, mock_admin, monkeypatch):
        monkeypatch.setattr(
            mock_admin,
            "_collect_log_ids",
            lambda filt=None: [],
        )
        for status in ("SUCCESS", "ERROR", "FATAL"):
            result = mock_admin.delete_logs(status=status)
            assert result == 0
