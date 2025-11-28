"""
Unit tests for Claude AI provider.

Tests cover:
- Provider properties (name, display_name)
- Claude CLI installation check
- Docker volume configuration
- Configuration validation
"""

from unittest.mock import MagicMock, patch

from aibox.config.models import Config, ProjectConfig
from aibox.providers.claude import ClaudeProvider


class TestClaudeProviderProperties:
    """Tests for Claude provider properties."""

    def test_name_property(self) -> None:
        """Test provider name is 'claude'."""
        provider = ClaudeProvider()
        assert provider.name == "claude"

    def test_display_name_property(self) -> None:
        """Test provider display name is human-readable."""
        provider = ClaudeProvider()
        assert provider.display_name == "Claude CLI"

    def test_mount_paths(self) -> None:
        """Test mount paths include only directory (not .claude.json file).

        Note: .claude.json is NOT mounted as a bind mount to avoid Docker issues.
        Instead, it's persisted via wrapper script (copy on startup/shutdown).
        """
        provider = ClaudeProvider()
        assert provider.get_mount_paths() == [".claude"]


class TestClaudeProviderConfigValidation:
    """Tests for Claude provider config validation.

    Note: API key validation is NOT performed.
    Claude CLI handles authentication independently.
    """

    def test_validate_config_succeeds(self) -> None:
        """Test validation passes - Claude handles auth independently."""
        provider = ClaudeProvider()
        config = Config(project=ProjectConfig(name="test"))

        # Should not raise any exception
        provider.validate_config(config)


class TestClaudeProviderInstallation:
    """Tests for Claude CLI installation detection."""

    def test_is_installed_when_claude_available(self) -> None:
        """Test is_installed returns True when Claude CLI is available."""
        provider = ClaudeProvider()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "claude 1.0.0"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = provider.is_installed()

            assert result is True
            mock_run.assert_called_once_with(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_is_installed_when_claude_not_found(self) -> None:
        """Test is_installed returns False when Claude CLI not found."""
        provider = ClaudeProvider()

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = provider.is_installed()
            assert result is False

    def test_is_installed_when_claude_fails(self) -> None:
        """Test is_installed returns False when Claude CLI fails."""
        provider = ClaudeProvider()

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = provider.is_installed()
            assert result is False


class TestClaudeProviderEnvironmentVariables:
    """Tests for Claude provider environment variable configuration."""

    def test_get_docker_env_vars_returns_empty(self) -> None:
        """Test get_docker_env_vars returns empty dict - Claude handles auth independently."""
        provider = ClaudeProvider()

        env_vars = provider.get_docker_env_vars()

        # Should return empty dict - Claude CLI handles auth independently
        assert env_vars == {}
