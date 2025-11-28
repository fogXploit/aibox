"""
Provider registry for managing AI provider implementations.

This module provides a central registry for discovering and instantiating
AI providers. It supports:
- Built-in providers (Claude, Gemini, OpenAI)
- Custom provider registration (for plugins)
- Provider discovery and listing
- Factory method for creating provider instances

The registry is implemented as a class with static methods to avoid
global state issues and support testing.
"""

from typing import Any

from aibox.providers.base import AIProvider
from aibox.providers.claude import ClaudeProvider
from aibox.providers.gemini import GeminiProvider
from aibox.providers.openai import OpenAIProvider
from aibox.utils.errors import ProviderError, ProviderNotFoundError


class ProviderRegistry:
    """
    Central registry for AI provider implementations.

    This class manages the mapping between provider names and their
    implementation classes. It provides factory methods to create
    provider instances and discovery methods to list available providers.

    The registry comes pre-populated with built-in providers:
    - claude: ClaudeProvider (fully implemented in v1.0)
    - gemini: GeminiProvider (placeholder for v1.1)
    - openai: OpenAIProvider (placeholder for v1.2)

    Custom providers can be registered for plugin support.

    Example:
        >>> # Get a provider instance
        >>> provider = ProviderRegistry.get_provider("claude")
        >>> provider.name
        'claude'

        >>> # List all available providers
        >>> ProviderRegistry.list_providers()
        ['claude', 'gemini', 'openai']

        >>> # Get detailed information about providers
        >>> details = ProviderRegistry.get_provider_details()
        >>> details['claude']['display_name']
        'Claude CLI'
    """

    # Built-in provider mapping: name -> provider class
    _providers: dict[str, type[AIProvider]] = {
        "claude": ClaudeProvider,
        "gemini": GeminiProvider,
        "openai": OpenAIProvider,
    }

    @classmethod
    def get_provider(cls, name: str) -> AIProvider:
        """
        Get a provider instance by name.

        This factory method creates and returns an instance of the requested
        provider. Provider names are case-insensitive.

        Args:
            name: Provider name (e.g., "claude", "gemini", "openai")

        Returns:
            An instance of the requested provider

        Raises:
            ProviderNotFoundError: If the provider name is not registered

        Example:
            >>> provider = ProviderRegistry.get_provider("claude")
            >>> provider.is_installed()
            True
        """
        # Normalize provider name to lowercase
        provider_name = name.lower()

        # Check if provider is registered
        if provider_name not in cls._providers:
            available = ", ".join(sorted(cls._providers.keys()))
            raise ProviderNotFoundError(
                f"AI provider '{name}' not found",
                suggestion=f"Available providers: {available}",
            )

        # Get provider class and instantiate it
        provider_class = cls._providers[provider_name]
        return provider_class()

    @classmethod
    def list_providers(cls) -> list[str]:
        """
        List all registered provider names.

        Returns:
            Sorted list of lowercase provider names

        Example:
            >>> ProviderRegistry.list_providers()
            ['claude', 'gemini', 'openai']
        """
        return sorted(cls._providers.keys())

    @classmethod
    def get_provider_details(cls) -> dict[str, dict[str, Any]]:
        """
        Get detailed information about all providers.

        Returns a dictionary mapping provider names to their details,
        including display name and implementation status.

        Returns:
            Dictionary mapping provider names to detail dictionaries with keys:
            - display_name: Human-readable provider name
            - implemented: Whether provider is fully implemented (vs placeholder)

        Example:
            >>> details = ProviderRegistry.get_provider_details()
            >>> details['claude']
            {
                'display_name': 'Claude CLI',
                'implemented': True
            }
        """
        details = {}

        for name, provider_class in cls._providers.items():
            # Create temporary instance to get properties
            provider = provider_class()

            # Determine if provider is implemented by checking if
            # is_installed raises NotImplementedError
            implemented = True
            try:
                # Try calling is_installed to see if it's implemented
                # We don't care about the result, just whether it raises
                provider.is_installed()
            except NotImplementedError:
                implemented = False
            except Exception:
                # Any other exception means the method is implemented
                # (even if it fails for other reasons like missing dependencies)
                implemented = True

            details[name] = {
                "display_name": provider.display_name,
                "implemented": implemented,
            }

        return details

    @classmethod
    def register_provider(cls, name: str, provider_class: type[AIProvider]) -> None:
        """
        Register a custom provider.

        This method allows plugins to register additional AI providers
        beyond the built-in ones. Provider names must be unique.

        Args:
            name: Provider name (will be normalized to lowercase)
            provider_class: The provider class (must inherit from AIProvider)

        Raises:
            ProviderError: If provider name is already registered

        Example:
            >>> class MyProvider(AIProvider):
            ...     # ... implement abstract methods
            ...     pass
            >>> ProviderRegistry.register_provider("myprovider", MyProvider)
        """
        provider_name = name.lower()

        if provider_name in cls._providers:
            raise ProviderError(
                f"Provider '{name}' is already registered",
                suggestion="Use a different provider name or unregister the existing one first",
            )

        cls._providers[provider_name] = provider_class
