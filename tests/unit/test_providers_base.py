"""
Unit tests for AIProvider abstract base class.

Tests cover:
- Abstract base class interface definition
- Required properties (name, display_name)
- Required methods (is_installed, get_docker_volumes, etc.)
- Concrete implementation validation
- Type safety and inheritance
"""

from abc import ABC

import pytest

from aibox.config.models import Config, ProjectConfig
from aibox.providers.base import AIProvider


class ConcreteProvider(AIProvider):
    """Concrete implementation of AIProvider for testing."""

    @property
    def name(self) -> str:
        """Return provider name."""
        return "test-provider"

    @property
    def display_name(self) -> str:
        """Return provider display name."""
        return "Test Provider"

    def is_installed(self) -> bool:
        """Check if provider is installed."""
        return True

    def get_docker_env_vars(self) -> dict[str, str]:
        """Get Docker environment variables."""
        return {}

    def validate_config(self, _config: Config) -> None:
        """Validate provider configuration."""
        return None

    def get_mount_paths(self) -> list[str]:
        """Get mount paths."""
        return [".test"]

    def get_cli_command(self) -> list[str]:
        """Get CLI command."""
        return ["test-cli"]


class IncompleteProvider(AIProvider):
    """Incomplete provider for testing abstract enforcement."""

    @property
    def name(self) -> str:
        """Return provider name."""
        return "incomplete"


class TestAIProviderInterface:
    """Tests for AIProvider abstract base class interface."""

    def test_is_abstract_base_class(self) -> None:
        """Test that AIProvider is an abstract base class."""
        assert issubclass(AIProvider, ABC)

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test that AIProvider cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            AIProvider()  # type: ignore[abstract]

    def test_cannot_instantiate_incomplete_implementation(self) -> None:
        """Test that incomplete implementations cannot be instantiated."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteProvider()  # type: ignore[abstract]

    def test_can_instantiate_complete_implementation(self) -> None:
        """Test that complete implementations can be instantiated."""
        provider = ConcreteProvider()
        assert isinstance(provider, AIProvider)
        assert isinstance(provider, ConcreteProvider)


class TestAIProviderProperties:
    """Tests for AIProvider property requirements."""

    def test_name_property(self) -> None:
        """Test name property returns string."""
        provider = ConcreteProvider()
        assert isinstance(provider.name, str)
        assert provider.name == "test-provider"

    def test_display_name_property(self) -> None:
        """Test display_name property returns string."""
        provider = ConcreteProvider()
        assert isinstance(provider.display_name, str)
        assert provider.display_name == "Test Provider"


class TestAIProviderMethods:
    """Tests for AIProvider method requirements."""

    def test_is_installed_method(self) -> None:
        """Test is_installed method returns boolean."""
        provider = ConcreteProvider()
        result = provider.is_installed()
        assert isinstance(result, bool)
        assert result is True

    def test_get_docker_env_vars_method(self) -> None:
        """Test get_docker_env_vars method returns dict."""
        provider = ConcreteProvider()
        env_vars = provider.get_docker_env_vars()

        assert isinstance(env_vars, dict)
        assert all(isinstance(k, str) and isinstance(v, str) for k, v in env_vars.items())

    def test_validate_config_method(self) -> None:
        """Test validate_config method accepts Config object."""
        provider = ConcreteProvider()
        config = Config(project=ProjectConfig(name="test"))

        # Should not raise any exception
        provider.validate_config(config)

    def test_get_mount_paths_method(self) -> None:
        """Test get_mount_paths method returns list of strings."""
        provider = ConcreteProvider()
        mount_paths = provider.get_mount_paths()

        assert isinstance(mount_paths, list)
        assert all(isinstance(p, str) for p in mount_paths)
        assert mount_paths == [".test"]


class TestAIProviderInheritance:
    """Tests for AIProvider inheritance patterns."""

    def test_concrete_provider_is_ai_provider(self) -> None:
        """Test concrete implementation is instance of AIProvider."""
        provider = ConcreteProvider()
        assert isinstance(provider, AIProvider)

    def test_concrete_provider_has_all_required_attributes(self) -> None:
        """Test concrete implementation has all required attributes."""
        provider = ConcreteProvider()

        # Properties
        assert hasattr(provider, "name")
        assert hasattr(provider, "display_name")

        # Methods
        assert hasattr(provider, "is_installed")
        assert hasattr(provider, "get_docker_env_vars")
        assert hasattr(provider, "validate_config")
        assert hasattr(provider, "get_mount_paths")

    def test_concrete_provider_methods_are_callable(self) -> None:
        """Test all required methods are callable."""
        provider = ConcreteProvider()

        assert callable(provider.is_installed)
        assert callable(provider.get_docker_env_vars)
        assert callable(provider.validate_config)
        assert callable(provider.get_mount_paths)
