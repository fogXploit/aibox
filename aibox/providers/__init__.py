"""
AI provider implementations and registry.

This package provides:
- AIProvider abstract base class defining the provider interface
- ClaudeProvider for Claude CLI
- GeminiProvider for Google's Antigravity CLI (`agy`; provider key stays "gemini")
- OpenAIProvider for OpenAI Codex CLI
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
