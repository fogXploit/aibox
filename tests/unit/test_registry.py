"""
Unit tests for provider registry system.

Tests cover:
- Provider registration and discovery
- Factory method for creating provider instances
- Listing available providers
- Error handling for unknown providers
- Registry singleton behavior
"""

from unittest.mock import MagicMock, patch

import pytest

from aibox.config.models import Config
from aibox.providers.base import AIProvider
from aibox.providers.claude import ClaudeProvider
from aibox.providers.gemini import GeminiProvider
from aibox.providers.openai import OpenAIProvider
from aibox.providers.registry import ProviderRegistry
from aibox.utils.errors import ProviderNotFoundError


class TestProviderRegistryBasics:
    """Tests for basic provider registry functionality."""

    def test_get_provider_returns_claude(self) -> None:
        """Test get_provider returns ClaudeProvider instance for 'claude'."""
        provider = ProviderRegistry.get_provider("claude")

        assert isinstance(provider, ClaudeProvider)
        assert isinstance(provider, AIProvider)
        assert provider.name == "claude"

    def test_get_provider_returns_gemini(self) -> None:
        """Test get_provider returns GeminiProvider instance for 'gemini'."""
        provider = ProviderRegistry.get_provider("gemini")

        assert isinstance(provider, GeminiProvider)
        assert isinstance(provider, AIProvider)
        assert provider.name == "gemini"

    def test_get_provider_returns_openai(self) -> None:
        """Test get_provider returns OpenAIProvider instance for 'openai'."""
        provider = ProviderRegistry.get_provider("openai")

        assert isinstance(provider, OpenAIProvider)
        assert isinstance(provider, AIProvider)
        assert provider.name == "openai"

    def test_get_provider_case_insensitive(self) -> None:
        """Test get_provider handles case-insensitive provider names."""
        provider_upper = ProviderRegistry.get_provider("CLAUDE")
        provider_mixed = ProviderRegistry.get_provider("Claude")

        assert isinstance(provider_upper, ClaudeProvider)
        assert isinstance(provider_mixed, ClaudeProvider)

    def test_get_provider_raises_on_unknown_provider(self) -> None:
        """Test get_provider raises ProviderNotFoundError for unknown provider."""
        # Try to get a provider that doesn't exist
        with pytest.raises(ProviderNotFoundError) as exc_info:
            ProviderRegistry.get_provider("unknown")

        error = exc_info.value
        assert "unknown" in error.message.lower()
        assert error.suggestion is not None
        # Should list available providers in suggestion
        assert "claude" in error.suggestion.lower()


class TestProviderRegistryListing:
    """Tests for listing available providers."""

    def test_list_providers_returns_all_providers(self) -> None:
        """Test list_providers returns all registered provider names."""
        providers = ProviderRegistry.list_providers()

        assert isinstance(providers, list)
        assert "claude" in providers
        assert "gemini" in providers
        assert "openai" in providers

    def test_list_providers_returns_lowercase_names(self) -> None:
        """Test list_providers returns lowercase provider names."""
        providers = ProviderRegistry.list_providers()

        assert all(name.islower() for name in providers)

    def test_list_providers_is_sorted(self) -> None:
        """Test list_providers returns sorted list of provider names."""
        providers = ProviderRegistry.list_providers()

        assert providers == sorted(providers)

    def test_list_providers_count(self) -> None:
        """Test list_providers returns expected number of providers."""
        providers = ProviderRegistry.list_providers()

        # v1.0 should have exactly 3 providers: claude, gemini, openai
        assert len(providers) == 3


class TestProviderRegistryDetails:
    """Tests for getting detailed provider information."""

    @patch("subprocess.run")
    def test_get_provider_details_returns_info(self, mock_run: MagicMock) -> None:
        """Test get_provider_details returns provider information."""
        # Mock subprocess.run to avoid hanging on codex --version check
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        details = ProviderRegistry.get_provider_details()

        assert isinstance(details, dict)
        assert "claude" in details
        assert "gemini" in details
        assert "openai" in details

    @patch("subprocess.run")
    def test_get_provider_details_includes_display_name(self, mock_run: MagicMock) -> None:
        """Test provider details include display names."""
        # Mock subprocess.run to avoid hanging on codex --version check
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        details = ProviderRegistry.get_provider_details()

        assert details["claude"]["display_name"] == "Claude CLI"
        assert details["gemini"]["display_name"] == "Gemini CLI"
        assert details["openai"]["display_name"] == "Codex CLI"

    @patch("subprocess.run")
    def test_get_provider_details_includes_status(self, mock_run: MagicMock) -> None:
        """Test provider details include implementation status."""
        # Mock subprocess.run to avoid hanging on codex --version check
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        details = ProviderRegistry.get_provider_details()

        # All three providers should be fully implemented
        assert details["claude"]["implemented"] is True
        assert details["openai"]["implemented"] is True
        assert details["gemini"]["implemented"] is True


class TestProviderRegistryCustomProviders:
    """Tests for registering custom providers."""

    def test_register_provider_adds_custom_provider(self) -> None:
        """Test register_provider allows adding custom provider."""

        class CustomProvider(AIProvider):
            @property
            def name(self) -> str:
                return "custom"

            @property
            def display_name(self) -> str:
                return "Custom Provider"

            def is_installed(self) -> bool:
                return True

            def get_docker_env_vars(self) -> dict[str, str]:
                return {}

            def validate_config(self, config: Config) -> None:
                pass

            def get_mount_paths(self) -> list[str]:
                return [".custom"]

            def get_cli_command(self) -> list[str]:
                return ["custom-cli"]

        # Register custom provider
        ProviderRegistry.register_provider("custom", CustomProvider)

        # Should be able to get it
        provider = ProviderRegistry.get_provider("custom")

        assert isinstance(provider, CustomProvider)
        assert provider.name == "custom"

        # Clean up - unregister for other tests
        ProviderRegistry._providers.pop("custom", None)

    def test_register_provider_raises_on_duplicate(self) -> None:
        """Test register_provider raises error when overwriting existing provider."""
        from aibox.utils.errors import ProviderError

        with pytest.raises(ProviderError) as exc_info:
            ProviderRegistry.register_provider("claude", ClaudeProvider)

        assert "already registered" in str(exc_info.value).lower()
