from __future__ import annotations

import os

import pytest


@pytest.fixture
def mock_conn(monkeypatch):
    """Return a PocketLog instance with authentication bypassed."""
    from pocketlogpy._base import PocketLogBase

    monkeypatch.setattr(PocketLogBase, "_authenticate", staticmethod(lambda *a: "fake-token"))
    from pocketlogpy import PocketLog

    return PocketLog(url="https://x.pockethost.io", email="a@b.com", password="pw")


@pytest.fixture
def mock_admin(monkeypatch):
    """Return a PocketLogAdmin instance with authentication bypassed."""
    from pocketlogpy._base import PocketLogBase

    monkeypatch.setattr(PocketLogBase, "_authenticate", staticmethod(lambda *a: "fake-token"))
    from pocketlogpy import PocketLogAdmin

    return PocketLogAdmin(url="https://x.pockethost.io", email="admin@b.com", password="pw")


@pytest.fixture
def env_clear(monkeypatch):
    """Clear all pocketlog environment variables."""
    for var in (
        "POCKETLOG_URL",
        "POCKETLOG_EMAIL",
        "POCKETLOG_PASSWORD",
        "POCKETLOG_ADMIN_EMAIL",
        "POCKETLOG_ADMIN_PASSWORD",
    ):
        monkeypatch.delenv(var, raising=False)
