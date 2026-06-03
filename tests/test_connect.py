from __future__ import annotations

import pytest

from pocketlogpy import PocketLog, PocketLogAdmin


class TestPocketLogConnect:
    def test_errors_on_missing_url(self, monkeypatch, env_clear):
        monkeypatch.setenv("POCKETLOG_EMAIL", "a@b.com")
        monkeypatch.setenv("POCKETLOG_PASSWORD", "pw")
        with pytest.raises(ValueError, match="URL is required"):
            PocketLog()

    def test_errors_on_missing_email(self, monkeypatch, env_clear):
        monkeypatch.setenv("POCKETLOG_URL", "https://x.pockethost.io")
        monkeypatch.setenv("POCKETLOG_PASSWORD", "pw")
        with pytest.raises(ValueError, match="Email is required"):
            PocketLog()

    def test_errors_on_missing_password(self, monkeypatch, env_clear):
        monkeypatch.setenv("POCKETLOG_URL", "https://x.pockethost.io")
        monkeypatch.setenv("POCKETLOG_EMAIL", "a@b.com")
        with pytest.raises(ValueError, match="Password is required"):
            PocketLog()

    def test_uses_env_vars(self, monkeypatch, env_clear):
        from pocketlogpy._base import PocketLogBase

        monkeypatch.setenv("POCKETLOG_URL", "https://x.pockethost.io")
        monkeypatch.setenv("POCKETLOG_EMAIL", "a@b.com")
        monkeypatch.setenv("POCKETLOG_PASSWORD", "pw")
        monkeypatch.setattr(PocketLogBase, "_authenticate", staticmethod(lambda *a: "tok"))

        conn = PocketLog()
        assert conn.url == "https://x.pockethost.io"
        assert conn.token == "tok"

    def test_strips_trailing_slash(self, monkeypatch):
        from pocketlogpy._base import PocketLogBase

        monkeypatch.setattr(PocketLogBase, "_authenticate", staticmethod(lambda *a: "tok"))
        conn = PocketLog(url="https://x.pockethost.io/", email="a@b.com", password="pw")
        assert conn.url == "https://x.pockethost.io"


class TestPocketLogAdminConnect:
    def test_errors_on_missing_admin_email(self, monkeypatch, env_clear):
        monkeypatch.setenv("POCKETLOG_URL", "https://x.pockethost.io")
        monkeypatch.setenv("POCKETLOG_ADMIN_PASSWORD", "pw")
        with pytest.raises(ValueError, match="Admin email is required"):
            PocketLogAdmin()

    def test_errors_on_missing_admin_password(self, monkeypatch, env_clear):
        monkeypatch.setenv("POCKETLOG_URL", "https://x.pockethost.io")
        monkeypatch.setenv("POCKETLOG_ADMIN_EMAIL", "admin@b.com")
        with pytest.raises(ValueError, match="Admin password is required"):
            PocketLogAdmin()

    def test_uses_admin_env_vars(self, monkeypatch, env_clear):
        from pocketlogpy._base import PocketLogBase

        monkeypatch.setenv("POCKETLOG_URL", "https://x.pockethost.io")
        monkeypatch.setenv("POCKETLOG_ADMIN_EMAIL", "admin@b.com")
        monkeypatch.setenv("POCKETLOG_ADMIN_PASSWORD", "pw")
        monkeypatch.setattr(PocketLogBase, "_authenticate", staticmethod(lambda *a: "tok"))

        admin = PocketLogAdmin()
        assert admin.url == "https://x.pockethost.io"
        assert admin.token == "tok"
