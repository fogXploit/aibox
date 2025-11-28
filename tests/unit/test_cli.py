"""Unit tests for CLI."""

from typer.testing import CliRunner

from aibox import __version__
from aibox.cli.main import app

runner = CliRunner()


def test_version():
    """Test --version flag."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"aibox v{__version__}" in result.stdout


def test_help():
    """Test --help flag."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Container-Based Multi-AI Development Environment" in result.stdout
