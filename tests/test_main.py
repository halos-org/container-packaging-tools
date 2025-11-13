"""Unit tests for __main__ module."""

import subprocess
import sys
from pathlib import Path


def test_main_entry_point():
    """Test that __main__.py can be executed as a module."""
    # Run the module as `python -m generate_container_packages --help`
    result = subprocess.run(
        [sys.executable, "-m", "generate_container_packages", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "generate-container-packages" in result.stdout
    assert "INPUT_DIR" in result.stdout


def test_main_version():
    """Test that __main__.py responds to --version."""
    result = subprocess.run(
        [sys.executable, "-m", "generate_container_packages", "--version"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "0.1.0" in result.stdout or "0.1.0" in result.stderr
