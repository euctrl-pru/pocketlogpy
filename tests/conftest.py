"""Shared pytest fixtures."""
import pytest
from pocketlogpy import Connection


@pytest.fixture
def conn():
    return Connection(url="https://test.pockethost.io", token="test-token")


@pytest.fixture
def admin_conn():
    return Connection(url="https://test.pockethost.io", token="admin-token")
