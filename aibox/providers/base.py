"""
Abstract base class for AI provider implementations.

This module defines the AIProvider interface that all AI providers (Claude, Gemini, OpenAI)
must implement. The interface ensures consistent behavior across different AI providers and
provides a contract for:
- Installation detection and setup
- Docker volume and environment configuration
- Configuration validation

All concrete provider implementations must inherit from AIProvider and implement all
abstract methods and properties.
"""

from abc import ABC, abstractmethod

from aibox.config.models import Config


class AIProvider(ABC):
    """
    Abstract base class for AI provider implementations.

    This class defines the interface that all AI providers must implement.
    Concrete implementations must provide:
    - Provider identification (name, display_name)
    - Installation detection and setup procedures
    - Docker volume mounts for provider-specific configuration
    - Environment variable configuration for containers
    - Configuration validation

    Authentication is handled by each AI provider's CLI independently, not by aibox.

    Example:
        class ClaudeProvider(AIProvider):
            @property
            def name(self) -> str:
                return "claude"

            @property
            def display_name(self) -> str:
                return "Claude CLI"

            def is_installed(self) -> bool:
                # Check if Claude CLI is available
                ...

            # ... implement other abstract methods
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get the provider identifier (used internally).

        Returns:
            Lowercase identifier string (e.g., "claude", "gemini", "openai")

        Example:
            >>> provider.name
            'claude'
        """

    @property
    @abstractmethod
    def display_name(self) -> str:
        """
        Get the human-readable provider name (for UI/logging).

        Returns:
            Display name string (e.g., "Claude CLI", "Gemini CLI")

        Example:
            >>> provider.display_name
            'Claude CLI'
        """

    @abstractmethod
    def is_installed(self) -> bool:
        """
        Check if the AI provider CLI is installed and available.

        This method should check if the provider's CLI tool is accessible,
        typically by running a version check command.

        Returns:
            True if provider CLI is installed and accessible, False otherwise

        Example:
            >>> provider.is_installed()
            True
        """

    @abstractmethod
    def get_docker_env_vars(self) -> dict[str, str]:
        """
        Get environment variables to pass to Docker container.

        This method returns environment variables needed by the provider.
        Most providers handle authentication independently and return an empty dict.

        Returns:
            Dictionary of environment variable names and values

        Example:
            >>> provider.get_docker_env_vars()
            {}
        """

    @abstractmethod
    def validate_config(self, config: Config) -> None:
        """
        Validate provider-specific configuration.

        This method checks that the configuration is valid for this provider.
        Most providers perform minimal validation as authentication is handled
        by the AI CLI itself.

        Args:
            config: The aibox configuration to validate

        Raises:
            InvalidConfigError: If configuration is invalid for this provider

        Example:
            >>> provider.validate_config(config)
            # No error - providers handle authentication themselves
        """

    @abstractmethod
    def get_mount_paths(self) -> list[str]:
        """
        Get all configuration paths to mount from host to container.

        Returns paths relative to home directory that need to be mounted for
        this provider to persist authentication and configuration across container
        restarts. Can include both files and directories.

        The VolumeManager automatically detects whether each path is a file or
        directory and mounts it appropriately to /home/aibox/<path> in the container.

        Returns:
            List of paths relative to home directory (e.g., [".claude", ".claude.json"])

        Example:
            >>> provider.get_mount_paths()
            ['.claude', '.claude.json']

        Note:
            - Paths that don't exist on host are automatically skipped
            - All mounts are read-write (mode: "rw")
            - Mounts are shared across all slots for session continuity
        """

    @abstractmethod
    def get_cli_command(self) -> list[str]:
        """
        Get the command to run the AI CLI interactively.

        This returns the command that should be executed to start the AI CLI
        in interactive mode (e.g., ["claude"] for Claude CLI, ["gemini"] for Gemini).

        Returns:
            List of command parts to execute

        Example:
            >>> provider.get_cli_command()
            ['claude']
        """

    def get_required_ports(
        self,
        force_auth_port: bool = False,
        project_storage_dir: str | None = None,
        slot_number: int | None = None,
    ) -> dict[str, tuple[str, int]] | dict[str, int] | dict[int, int]:
        """
        Get port mappings required for OAuth authentication.

        Many AI CLIs use OAuth flows that require a local web server for
        callback handling. This method returns the ports that need to be
        published from the container to the host.

        Returns:
            Dictionary mapping container port to host port binding.
            Format options:
            - {container_port: host_port} - Simple int mapping
            - {'port/tcp': ('0.0.0.0', host_port)} - Explicit binding to all interfaces
            Empty dict if no ports are required.

        Example:
            >>> provider.get_required_ports()
            {'1455/tcp': ('0.0.0.0', 1455)}  # Codex OAuth callback server

        Note:
            Ports are published when creating containers, allowing OAuth
            flows to work seamlessly from inside the container.
            Use '0.0.0.0' to bind to all interfaces for accessibility from host.
        Args:
            force_auth_port: Force exposing the auth port even if a cached session exists.
            project_storage_dir: Optional project storage directory (for slot-scoped state).
            slot_number: Optional slot number (for slot-scoped state).
        """
        _ = force_auth_port  # Hint: subclasses may use this
        _ = project_storage_dir
        _ = slot_number
        return {}
