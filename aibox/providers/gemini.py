"""
Gemini CLI provider implementation.

This module implements the AIProvider interface for Google's Gemini CLI.
It handles:
- Gemini CLI installation and detection
- Docker volume mounts for .gemini configuration directory

The Gemini provider mounts the project's .gemini directory to persist
configuration and session state across container restarts.

Authentication:
- OAuth handled by `gemini login` inside the container (random local port)
"""

import subprocess

from aibox.config.models import Config
from aibox.providers.base import AIProvider


class GeminiProvider(AIProvider):
    """
    Google Gemini CLI provider implementation.

    This provider integrates Google's Gemini CLI with aibox containers.
    Gemini CLI is a command-line interface for interacting with Google's
    Gemini AI models with advanced reasoning capabilities.

    Authentication is handled by the Gemini CLI via OAuth.
    Configuration is persisted in the .gemini directory across container restarts.

    Example:
        >>> provider = GeminiProvider()
        >>> provider.name
        'gemini'
        >>> provider.is_installed()
        True
        >>> provider.get_cli_command()
        ['gemini']
    """

    @property
    def name(self) -> str:
        """
        Get the provider identifier.

        Returns:
            The string "gemini"
        """
        return "gemini"

    @property
    def display_name(self) -> str:
        """
        Get the human-readable provider name.

        Returns:
            The string "Gemini CLI"
        """
        return "Gemini CLI"

    def is_installed(self) -> bool:
        """
        Check if Gemini CLI is installed and available.

        Runs `gemini --version` to verify the CLI is accessible.

        Returns:
            True if Gemini CLI is installed and responds to --version,
            False otherwise
        """
        try:
            result = subprocess.run(
                ["gemini", "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def get_docker_env_vars(self) -> dict[str, str]:
        """
        Get environment variables to pass to Docker container.

        Returns:
            Empty dictionary (Gemini CLI handles OAuth login interactively)
        """
        return {}

    def validate_config(self, config: Config) -> None:
        """
        Validate Gemini provider configuration.

        No validation is performed. Gemini CLI handles all authentication
        independently via its own config directory (.gemini/), which is
        mounted from the host to persist sessions across container restarts.

        Args:
            config: The aibox configuration (not currently used)
        """
        # No validation needed - Gemini CLI handles authentication independently

    def get_mount_paths(self) -> list[str]:
        """
        Get all configuration paths for Gemini CLI.

        Gemini CLI stores configuration in ~/.gemini/ directory.

        Returns:
            List containing [".gemini"]
        """
        return [".gemini"]

    def get_cli_command(self) -> list[str]:
        """
        Get the command to run Gemini CLI interactively.

        Returns:
            List containing the command ["gemini"]
        """
        return ["gemini"]
