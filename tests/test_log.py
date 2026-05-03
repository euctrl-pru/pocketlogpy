"""Tests for pl_log, pl_success, pl_error, pl_fatal."""
import pytest
from unittest.mock import patch, MagicMock

from pocketlogpy import pl_log, pl_success, pl_error, pl_fatal
from tests.helpers import make_mock_response, make_flows_response


SAMPLE_FLOW = {
    "id": "abc123", "name": "ectrl_data_load", "type": "data_job",
    "depends_on": [], "created": "2024-01-01 06:00:00.000",
}
LOG_RECORD = {
    "id": "log001", "flow": "abc123", "log_type": "data_job",
    "status": "SUCCESS", "message": "Done", "metadata": None,
    "created": "2024-01-01 06:01:00.000",
}


def _mock_get(*args, **kwargs):
    return make_flows_response([SAMPLE_FLOW])


class TestPlLog:
    def test_success_status(self, conn):
        with patch("requests.get", side_effect=_mock_get), \
             patch("requests.post",
                   return_value=make_mock_response(200, LOG_RECORD)):
            result = pl_log(conn, "ectrl_data_load", "SUCCESS",
                            log_type="data_job")
        assert result is not None

    def test_error_status(self, conn):
        with patch("requests.get", side_effect=_mock_get), \
             patch("requests.post",
                   return_value=make_mock_response(200, LOG_RECORD)):
            result = pl_log(conn, "ectrl_data_load", "ERROR",
                            log_type="data_job")
        assert result is not None

    def test_invalid_status_raises(self, conn):
        with pytest.raises(ValueError, match="status"):
            pl_log(conn, "ectrl_data_load", "INVALID", log_type="data_job")

    def test_empty_flow_raises(self, conn):
        with pytest.raises(ValueError, match="flow"):
            pl_log(conn, "", "SUCCESS", log_type="data_job")

    def test_empty_log_type_raises(self, conn):
        with pytest.raises(ValueError, match="log_type"):
            pl_log(conn, "ectrl_data_load", "SUCCESS", log_type="")

    def test_warns_on_failure_returns_none(self, conn):
        with patch("requests.get", side_effect=Exception("Network error")), \
             pytest.warns(UserWarning, match="failed to log"):
            result = pl_log(conn, "ectrl_data_load", "SUCCESS",
                            log_type="data_job")
        assert result is None

    def test_retries_on_failure(self, conn):
        with patch("requests.get", side_effect=_mock_get), \
             patch("requests.post", side_effect=Exception("Server error")), \
             patch("time.sleep"), \
             pytest.warns(UserWarning):
            result = pl_log(conn, "ectrl_data_load", "SUCCESS",
                            log_type="data_job")
        assert result is None


class TestShorthands:
    def test_pl_success(self, conn):
        with patch("pocketlogpy._log.pl_log",
                   return_value=LOG_RECORD) as mock_log:
            pl_success(conn, "my_flow", log_type="data_job", message="Done")
        mock_log.assert_called_once_with(
            conn, "my_flow", "SUCCESS",
            log_type="data_job", message="Done", metadata=None,
        )

    def test_pl_error(self, conn):
        with patch("pocketlogpy._log.pl_log", return_value=None) as mock_log:
            pl_error(conn, "my_flow", log_type="data_job", message="Oops")
        mock_log.assert_called_once_with(
            conn, "my_flow", "ERROR",
            log_type="data_job", message="Oops", metadata=None,
        )

    def test_pl_fatal(self, conn):
        with patch("pocketlogpy._log.pl_log", return_value=None) as mock_log:
            pl_fatal(conn, "my_flow", log_type="data_job", message="Critical")
        mock_log.assert_called_once_with(
            conn, "my_flow", "FATAL",
            log_type="data_job", message="Critical", metadata=None,
        )
