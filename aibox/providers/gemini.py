"""
Antigravity CLI provider implementation.

This module implements the AIProvider interface for Google's Antigravity CLI
(`agy`), the successor to the retired Gemini CLI. It handles:
- Antigravity CLI installation and detection
- Docker volume mounts for the .gemini configuration directory
  (Antigravity CLI reuses ~/.gemini)

The provider keeps the name "gemini" for config compatibility and mounts the
project's .gemini directory to persist configuration and session state across
container restarts.

Authentication:
- Google sign-in is triggered by running `agy` interactively inside the container
"""

import subprocess

from aibox.config.models import Config
from aibox.providers.base import AIProvider


class GeminiProvider(AIProvider):
    """
    Google Antigravity CLI provider implementation.

    This provider integrates Google's Antigravity CLI (`agy`), the successor
    to the retired Gemini CLI, with aibox containers. The provider name stays
    "gemini" for config compatibility, and Antigravity CLI still uses the
    ~/.gemini config directory.

    Authentication is handled by the Antigravity CLI via Google sign-in on
    first run. Configuration is persisted in the .gemini directory across
    container restarts.

    Example:
        >>> provider = GeminiProvider()
        >>> provider.name
        'gemini'
        >>> provider.is_installed()
        True
        >>> provider.get_cli_command()
        ['agy']
    """

    @property
    def name(self) -> str:
        """
        Get the provider identifier.

        Kept as "gemini" for config compatibility with existing setups.

        Returns:
            The string "gemini"
        """
        return "gemini"

    @property
    def display_name(self) -> str:
        """
        Get the human-readable provider name.

        Returns:
            The string "Antigravity CLI"
        """
        return "Antigravity CLI"

    def is_installed(self) -> bool:
        """
        Check if Antigravity CLI is installed and available.

        Runs `agy --version` to verify the CLI is accessible.

        Returns:
            True if Antigravity CLI is installed and responds to --version,
            False otherwise
        """
        try:
            result = subprocess.run(
                ["agy", "--version"],
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
            Empty dictionary (Antigravity CLI handles sign-in interactively)
        """
        return {}

    def validate_config(self, config: Config) -> None:
        """
        Validate provider configuration.

        No validation is performed. Antigravity CLI handles all authentication
        independently via its own config directory (.gemini/), which is
        mounted from the host to persist sessions across container restarts.

        Args:
            config: The aibox configuration (not currently used)
        """
        # No validation needed - Antigravity CLI handles authentication independently

    def get_mount_paths(self) -> list[str]:
        """
        Get all configuration paths for Antigravity CLI.

        Antigravity CLI reuses the ~/.gemini/ configuration directory.

        Returns:
            List containing [".gemini"]
        """
        return [".gemini"]

    def get_cli_command(self) -> list[str]:
        """
        Get the command to run Antigravity CLI interactively.

        Returns:
            List containing the command ["agy"]
        """
        return ["agy"]
