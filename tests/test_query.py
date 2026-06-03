from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pocketlogpy._utils import build_filter, format_timestamp
from pocketlogpy.models import LogEntry


class TestGetLogsValidation:
    def test_validates_status_argument(self, mock_conn):
        with pytest.raises(ValueError, match="'status' must be one of"):
            mock_conn.get_logs(status="INVALID")

    def test_accepts_valid_statuses(self, mock_conn, monkeypatch):
        monkeypatch.setattr(
            mock_conn,
            "_get",
            lambda path, **kw: {"items": [], "totalPages": 1},
        )
        for status in ("SUCCESS", "ERROR", "FATAL"):
            result = mock_conn.get_logs(status=status)
            assert result == []

    def test_returns_empty_list_when_no_results(self, mock_conn, monkeypatch):
        monkeypatch.setattr(
            mock_conn,
            "_get",
            lambda path, **kw: {"items": [], "totalPages": 1},
        )
        result = mock_conn.get_logs()
        assert result == []

    def test_returns_log_entry_objects(self, mock_conn, monkeypatch):
        monkeypatch.setattr(
            mock_conn,
            "_get",
            lambda path, **kw: {
                "items": [
                    {
                        "id": "log1",
                        "flow": "fid",
                        "log_type": "data_job",
                        "status": "SUCCESS",
                        "message": "ok",
                        "metadata": None,
                        "logged_by": "tester",
                        "logged_from": None,
                        "source_file": "run.py",
                        "source_repo": "myrepo",
                        "created": "2024-01-01 00:00:00",
                        "expand": {"flow": {"name": "myflow"}},
                    }
                ],
                "totalPages": 1,
            },
        )
        result = mock_conn.get_logs()
        assert len(result) == 1
        assert isinstance(result[0], LogEntry)
        assert result[0].flow == "myflow"
        assert result[0].status == "SUCCESS"
        assert result[0].logged_by == "tester"
        assert result[0].source_file == "run.py"


class TestFormatTimestamp:
    def test_handles_datetime(self):
        ts = datetime(2024, 6, 15, 8, 30, 0, tzinfo=timezone.utc)
        result = format_timestamp(ts)
        assert isinstance(result, str)
        assert "2024-06-15" in result

    def test_handles_iso_string(self):
        result = format_timestamp("2024-06-15T08:30:00Z")
        assert result == "2024-06-15T08:30:00Z"

    def test_returns_none_for_none(self):
        assert format_timestamp(None) is None


class TestBuildFilter:
    def test_returns_none_for_no_parts(self):
        assert build_filter(None, None) is None

    def test_combines_parts_with_and(self):
        result = build_filter('status = "ERROR"', 'flow.name = "myflow"')
        assert result == 'status = "ERROR" && flow.name = "myflow"'

    def test_skips_none_parts(self):
        result = build_filter('status = "ERROR"', None)
        assert result == 'status = "ERROR"'

    def test_all_none_returns_none(self):
        assert build_filter(None) is None
