"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def _set_temp_home(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Point HOME to a writable temporary directory for tests."""
    temp_home = tmp_path_factory.mktemp("home")
    # Ensure any code relying on HOME uses the temporary location
    import os

    os.environ["HOME"] = str(temp_home)
    return temp_home


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "version": "1.0",
        "project": {
            "name": "test-project",
            "profiles": ["python:3.12"],
            "ai": {
                "provider": "claude",
            },
            "mounts": [],
        },
    }
