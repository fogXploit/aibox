"""
Unit tests for Google Gemini provider.

Tests cover:
- Provider properties (name, display_name)
- Gemini CLI installation check
- Docker volume configuration
- Configuration validation
"""

from unittest.mock import MagicMock, patch

from aibox.config.models import Config, ProjectConfig
from aibox.providers.gemini import GeminiProvider


class TestGeminiProviderProperties:
    """Tests for Gemini provider properties."""

    def test_name_property(self) -> None:
        """Test provider name is 'gemini'."""
        provider = GeminiProvider()
        assert provider.name == "gemini"

    def test_display_name_property(self) -> None:
        """Test provider display name is human-readable."""
        provider = GeminiProvider()
        assert provider.display_name == "Gemini CLI"

    def test_mount_paths(self) -> None:
        """Test mount paths include directory."""
        provider = GeminiProvider()
        assert provider.get_mount_paths() == [".gemini"]

    def test_cli_command(self) -> None:
        """Test CLI command is 'gemini'."""
        provider = GeminiProvider()
        assert provider.get_cli_command() == ["gemini"]


class TestGeminiProviderConfigValidation:
    """Tests for Gemini provider config validation.

    Note: API key validation is NOT performed.
    Gemini CLI handles authentication independently.
    """

    def test_validate_config_succeeds(self) -> None:
        """Test validation passes - Gemini handles auth independently."""
        provider = GeminiProvider()
        config = Config(project=ProjectConfig(name="test"))

        # Should not raise any exception
        provider.validate_config(config)


class TestGeminiProviderInstallation:
    """Tests for Gemini CLI installation detection."""

    def test_is_installed_when_gemini_available(self) -> None:
        """Test is_installed returns True when Gemini CLI is available."""
        provider = GeminiProvider()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "gemini 1.0.0"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = provider.is_installed()

            assert result is True
            mock_run.assert_called_once_with(
                ["gemini", "--version"],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_is_installed_when_gemini_not_found(self) -> None:
        """Test is_installed returns False when Gemini CLI not found."""
        provider = GeminiProvider()

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = provider.is_installed()
            assert result is False

    def test_is_installed_when_gemini_fails(self) -> None:
        """Test is_installed returns False when Gemini CLI fails."""
        provider = GeminiProvider()

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = provider.is_installed()
            assert result is False


class TestGeminiProviderEnvironmentVariables:
    """Tests for Gemini provider environment variable configuration."""

    def test_get_docker_env_vars_with_api_key(self) -> None:
        """API keys are ignored; login flow handles auth."""
        provider = GeminiProvider()

        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-api-key"}):
            env_vars = provider.get_docker_env_vars()

            assert env_vars == {}

    def test_get_docker_env_vars_without_api_key(self) -> None:
        """No API key should result in empty env vars."""
        provider = GeminiProvider()

        with patch.dict("os.environ", {}, clear=True):
            env_vars = provider.get_docker_env_vars()

            assert env_vars == {}

    def test_get_docker_env_vars_with_google_api_key(self) -> None:
        """GOOGLE_API_KEY is also ignored."""
        provider = GeminiProvider()

        with patch.dict("os.environ", {"GOOGLE_API_KEY": "google-key"}, clear=True):
            env_vars = provider.get_docker_env_vars()

            assert env_vars == {}

    def test_get_docker_env_vars_prefers_gemini_key(self) -> None:
        """Both keys present should still result in empty env vars."""
        provider = GeminiProvider()

        with patch.dict(
            "os.environ",
            {"GOOGLE_API_KEY": "google-key", "GEMINI_API_KEY": "gemini-key"},
            clear=True,
        ):
            env_vars = provider.get_docker_env_vars()

            assert env_vars == {}
