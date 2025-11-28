"""
Unit tests for OpenAI Codex provider.

Tests cover:
- Provider properties (name, display_name)
- Codex CLI installation check
- Docker volume configuration
- Configuration validation
"""

from unittest.mock import MagicMock, patch

from aibox.config.models import Config, ProjectConfig
from aibox.providers.openai import OpenAIProvider


class TestOpenAIProviderProperties:
    """Tests for OpenAI/Codex provider properties."""

    def test_name_property(self) -> None:
        """Test provider name is 'openai'."""
        provider = OpenAIProvider()
        assert provider.name == "openai"

    def test_display_name_property(self) -> None:
        """Test provider display name is human-readable."""
        provider = OpenAIProvider()
        assert provider.display_name == "Codex CLI"

    def test_mount_paths(self) -> None:
        """Test mount paths include directory."""
        provider = OpenAIProvider()
        assert provider.get_mount_paths() == [".codex"]

    def test_cli_command(self) -> None:
        """Test CLI command runs codex directly."""
        provider = OpenAIProvider()
        assert provider.get_cli_command() == ["codex"]


class TestOpenAIProviderConfigValidation:
    """Tests for OpenAI/Codex provider config validation.

    Note: API key validation is NOT performed.
    Codex CLI handles authentication independently.
    """

    def test_validate_config_succeeds(self) -> None:
        """Test validation passes - Codex handles auth independently."""
        provider = OpenAIProvider()
        config = Config(project=ProjectConfig(name="test"))

        # Should not raise any exception
        provider.validate_config(config)


class TestOpenAIProviderInstallation:
    """Tests for Codex CLI installation detection."""

    def test_is_installed_when_codex_available(self) -> None:
        """Test is_installed returns True when Codex CLI is available."""
        provider = OpenAIProvider()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "codex 1.0.0"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = provider.is_installed()

            assert result is True
            mock_run.assert_called_once_with(
                ["codex", "--version"],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_is_installed_when_codex_not_found(self) -> None:
        """Test is_installed returns False when Codex CLI not found."""
        provider = OpenAIProvider()

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = provider.is_installed()
            assert result is False

    def test_is_installed_when_codex_fails(self) -> None:
        """Test is_installed returns False when Codex CLI fails."""
        provider = OpenAIProvider()

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = provider.is_installed()
            assert result is False


class TestOpenAIProviderEnvironmentVariables:
    """Tests for OpenAI/Codex provider environment variable configuration."""

    def test_get_docker_env_vars_returns_empty(self) -> None:
        """Test get_docker_env_vars returns empty dict - Codex handles auth independently."""
        provider = OpenAIProvider()

        env_vars = provider.get_docker_env_vars()

        # Should return empty dict - Codex CLI handles auth independently
        assert env_vars == {}


class TestOpenAIProviderPorts:
    """Tests for OpenAI/Codex provider port exposure logic."""

    def test_get_required_ports_without_session_exposes_fixed_port(
        self, tmp_path, monkeypatch
    ) -> None:
        """Port 1455 is exposed when no Codex session is present."""
        codex_dir = tmp_path / ".codex"
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        provider = OpenAIProvider()
        assert provider.get_required_ports() == {"1455/tcp": 1455}
        assert not codex_dir.exists()

    def test_get_required_ports_with_slot_scoped_session_skips_port(
        self, tmp_path, monkeypatch
    ) -> None:
        """Port is skipped when a session exists in slot-scoped .codex directory."""
        storage_dir = "project-abc12345"
        slot_codex_dir = (
            tmp_path / ".aibox" / "projects" / storage_dir / "slots" / "slot-1" / ".codex"
        )
        slot_codex_dir.mkdir(parents=True)
        (slot_codex_dir / "config.json").write_text('{"access_token": "abc"}')
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        provider = OpenAIProvider()
        assert provider.get_required_ports(project_storage_dir=storage_dir, slot_number=1) == {}

    def test_get_required_ports_forced_always_exposes_fixed_port(
        self, tmp_path, monkeypatch
    ) -> None:
        """Force flag always exposes port 1455, even with a session."""
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        (codex_dir / "config.json").write_text('{"access_token": "abc"}')
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        provider = OpenAIProvider()
        assert provider.get_required_ports(force_auth_port=True) == {"1455/tcp": 1455}
