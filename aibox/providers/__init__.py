"""
AI provider implementations and registry.

This package provides:
- AIProvider abstract base class defining the provider interface
- ClaudeProvider fully implemented for Claude CLI (v1.0)
- GeminiProvider placeholder (coming in v1.1)
- OpenAIProvider placeholder (coming in v1.2)
- ProviderRegistry for managing and discovering providers

Example:
    >>> from aibox.providers import ProviderRegistry
    >>> provider = ProviderRegistry.get_provider("claude")
    >>> provider.is_installed()
    True

    >>> providers = ProviderRegistry.list_providers()
    >>> print(providers)
    ['claude', 'gemini', 'openai']
"""

from aibox.providers.base import AIProvider
from aibox.providers.claude import ClaudeProvider
from aibox.providers.gemini import GeminiProvider
from aibox.providers.openai import OpenAIProvider
from aibox.providers.registry import ProviderRegistry

__all__ = [
    "AIProvider",
    "ClaudeProvider",
    "GeminiProvider",
    "OpenAIProvider",
    "ProviderRegistry",
]
