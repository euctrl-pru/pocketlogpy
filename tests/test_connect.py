"""Tests for pl_connect and pl_connect_admin."""
import pytest
from unittest.mock import patch, MagicMock

from pocketlogpy import pl_connect, pl_connect_admin, Connection


def _auth_ok(token="test-token"):
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"token": token}
    return m


def _auth_fail():
    m = MagicMock()
    m.status_code = 401
    m.json.return_value = {"message": "Invalid credentials"}
    m.content = b"error"
    return m


class TestPlConnect:
    def test_returns_connection(self):
        with patch("requests.post", return_value=_auth_ok()):
            conn = pl_connect(
                url="https://myapp.pockethost.io",
                email="user@example.com",
                password="secret",
            )
        assert isinstance(conn, Connection)
        assert conn.url == "https://myapp.pockethost.io"
        assert conn.token == "test-token"

    def test_strips_trailing_slash(self):
        with patch("requests.post", return_value=_auth_ok()):
            conn = pl_connect(
                url="https://myapp.pockethost.io/",
                email="u@e.com",
                password="p",
            )
        assert conn.url == "https://myapp.pockethost.io"

    def test_reads_env_vars(self, monkeypatch):
        monkeypatch.setenv("POCKETLOG_URL", "https://env.pockethost.io")
        monkeypatch.setenv("POCKETLOG_EMAIL", "env@example.com")
        monkeypatch.setenv("POCKETLOG_PASSWORD", "env-secret")
        with patch("requests.post", return_value=_auth_ok()):
            conn = pl_connect()
        assert conn.url == "https://env.pockethost.io"

    def test_raises_on_missing_url(self):
        with pytest.raises(ValueError, match="URL"):
            pl_connect(url="", email="a@b.com", password="x")

    def test_raises_on_missing_email(self):
        with pytest.raises(ValueError, match="Email"):
            pl_connect(url="https://x.io", email="", password="x")

    def test_raises_on_missing_password(self):
        with pytest.raises(ValueError, match="Password"):
            pl_connect(url="https://x.io", email="a@b.com", password="")

    def test_raises_on_auth_failure(self):
        with patch("requests.post", return_value=_auth_fail()):
            with pytest.raises(RuntimeError, match="Authentication failed"):
                pl_connect(
                    url="https://x.io", email="bad@x.io", password="wrong"
                )

    def test_uses_users_collection(self):
        with patch("requests.post", return_value=_auth_ok()) as mock_post:
            pl_connect(url="https://x.io", email="u@e.com", password="p")
        assert "/users/" in mock_post.call_args[0][0]


class TestPlConnectAdmin:
    def test_returns_connection(self):
        with patch("requests.post", return_value=_auth_ok()):
            conn = pl_connect_admin(
                url="https://x.io", email="admin@x.io", password="s"
            )
        assert isinstance(conn, Connection)

    def test_reads_admin_env_vars(self, monkeypatch):
        monkeypatch.setenv("POCKETLOG_URL", "https://env.io")
        monkeypatch.setenv("POCKETLOG_ADMIN_EMAIL", "admin@env.io")
        monkeypatch.setenv("POCKETLOG_ADMIN_PASSWORD", "pw")
        with patch("requests.post", return_value=_auth_ok()):
            conn = pl_connect_admin()
        assert conn.url == "https://env.io"

    def test_uses_superusers_collection(self):
        with patch("requests.post", return_value=_auth_ok()) as mock_post:
            pl_connect_admin(url="https://x.io", email="a@x.io", password="p")
        assert "_superusers" in mock_post.call_args[0][0]

    def test_raises_on_missing_admin_email(self):
        with pytest.raises(ValueError, match="Admin email"):
            pl_connect_admin(url="https://x.io", email="", password="p")
