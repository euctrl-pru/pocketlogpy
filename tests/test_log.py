from __future__ import annotations

import warnings

import pytest

from pocketlogpy import LOG_TYPES, PocketLog
from pocketlogpy._utils import get_machine_info, get_source_file, get_source_repo, get_system_user, retry


class TestLogValidation:
    def test_validates_status_values(self, mock_conn):
        with pytest.raises(ValueError, match="'status' must be one of"):
            mock_conn.log("myflow", "INVALID", log_type="data_job")
        with pytest.raises(ValueError, match="'status' must be one of"):
            mock_conn.log("myflow", "success", log_type="data_job")
        with pytest.raises(ValueError, match="'status' must be one of"):
            mock_conn.log("myflow", "", log_type="data_job")

    def test_validates_flow_argument(self, mock_conn):
        with pytest.raises(ValueError, match="'flow' must be"):
            mock_conn.log("", "SUCCESS", log_type="data_job")
        with pytest.raises(ValueError, match="'flow' must be"):
            mock_conn.log(123, "SUCCESS", log_type="data_job")

    def test_validates_log_type_argument(self, mock_conn):
        with pytest.raises(ValueError, match="'log_type' must be"):
            mock_conn.log("myflow", "SUCCESS", log_type="")
        with pytest.raises(ValueError, match="'log_type' must be"):
            mock_conn.log("myflow", "SUCCESS", log_type=123)


class TestLogRetry:
    def test_warns_and_returns_none_after_exhausting_retries(self, mock_conn, monkeypatch):
        call_count = 0

        def mock_resolve(flow_name):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("simulated HTTP error")

        monkeypatch.setattr(mock_conn, "_resolve_flow_id", mock_resolve)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = mock_conn.log("myflow", "SUCCESS", log_type="data_job")
            assert result is None
            assert len(w) == 1
            assert "failed to log event" in str(w[0].message)
        assert call_count == 3


class TestRetryUtil:
    def test_respects_times_parameter(self):
        count = 0

        def always_fails():
            nonlocal count
            count += 1
            raise RuntimeError("always fails")

        result = retry(always_fails, times=3, wait=0)
        assert count == 3
        assert isinstance(result, RuntimeError)

    def test_returns_value_on_success(self):
        result = retry(lambda: 42, times=3, wait=0)
        assert result == 42

    def test_stops_early_on_success(self):
        count = 0

        def succeeds_second_time():
            nonlocal count
            count += 1
            if count < 2:
                raise RuntimeError("not yet")
            return "done"

        result = retry(succeeds_second_time, times=3, wait=0)
        assert count == 2
        assert result == "done"


class TestConvenienceWrappers:
    def test_success_passes_through_params(self, mock_conn, monkeypatch):
        captured = {}

        def mock_log(flow, status, log_type, **kwargs):
            captured["status"] = status
            captured["log_type"] = log_type
            captured.update(kwargs)
            return None

        monkeypatch.setattr(mock_conn, "log", mock_log)

        mock_machine = {"machine": "TEST-PC", "os": "Windows", "user": "tester"}
        mock_conn.success(
            "myflow",
            log_type="data_job",
            logged_by="tester",
            logged_from=mock_machine,
            source_file="run.py",
            source_repo="myrepo",
        )
        assert captured["status"] == "SUCCESS"
        assert captured["log_type"] == "data_job"
        assert captured["logged_by"] == "tester"
        assert captured["logged_from"] == mock_machine
        assert captured["source_file"] == "run.py"
        assert captured["source_repo"] == "myrepo"

    def test_error_passes_through_params(self, mock_conn, monkeypatch):
        captured = {}

        def mock_log(flow, status, log_type, **kwargs):
            captured["status"] = status
            captured["log_type"] = log_type
            captured.update(kwargs)
            return None

        monkeypatch.setattr(mock_conn, "log", mock_log)

        mock_conn.error(
            "myflow",
            log_type="website_online",
            logged_by="bot",
            source_file="check.py",
            source_repo="ops",
        )
        assert captured["status"] == "ERROR"
        assert captured["log_type"] == "website_online"
        assert captured["logged_by"] == "bot"
        assert captured["source_file"] == "check.py"
        assert captured["source_repo"] == "ops"

    def test_fatal_passes_through_params(self, mock_conn, monkeypatch):
        captured = {}

        def mock_log(flow, status, log_type, **kwargs):
            captured["status"] = status
            captured["log_type"] = log_type
            captured.update(kwargs)
            return None

        monkeypatch.setattr(mock_conn, "log", mock_log)

        mock_conn.fatal(
            "myflow",
            log_type="data_job",
            logged_by="admin",
            source_file="etl.py",
            source_repo="pipeline",
        )
        assert captured["status"] == "FATAL"
        assert captured["log_type"] == "data_job"
        assert captured["logged_by"] == "admin"
        assert captured["source_file"] == "etl.py"
        assert captured["source_repo"] == "pipeline"


class TestLogTypes:
    def test_contains_expected_values(self):
        assert "data_job" in LOG_TYPES
        assert "website_online" in LOG_TYPES
        assert "website_status" in LOG_TYPES
        assert "email_check" in LOG_TYPES
        assert "db_check" in LOG_TYPES

    def test_is_tuple(self):
        assert isinstance(LOG_TYPES, tuple)


class TestAutoDetection:
    def test_get_machine_info_returns_expected_keys(self):
        info = get_machine_info()
        assert isinstance(info, dict)
        assert all(k in info for k in ("machine", "os", "os_version", "user"))
        assert info["os"]  # should not be empty

    def test_get_system_user_returns_nonempty_string(self):
        user = get_system_user()
        assert isinstance(user, str)
        assert len(user) > 0

    def test_get_source_file_returns_string_or_none(self):
        result = get_source_file()
        assert result is None or isinstance(result, str)

    def test_get_source_repo_returns_string_or_none(self):
        result = get_source_repo()
        assert result is None or isinstance(result, str)
