"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture(autouse=True)
def set_halos_hostname(monkeypatch):
    """Set HALOS_HOSTNAME for all tests.

    This is required because registry generation needs a hostname.
    Using a test-specific placeholder that clearly indicates this is a test.
    """
    monkeypatch.setenv("HALOS_HOSTNAME", "test.local")
