"""
Codex CLI provider implementation.

This module implements the AIProvider interface for Codex CLI.
It handles:
- Codex CLI installation and detection
- Docker volume mounts for .codex configuration directory

The Codex provider mounts the project's .codex directory to persist
configuration and session state across container restarts. Authentication
is handled entirely by the Codex CLI itself.
"""

import subprocess
from pathlib import Path

from aibox.config.models import Config
from aibox.providers.base import AIProvider


class OpenAIProvider(AIProvider):
    """
    OpenAI Codex CLI provider implementation.

    This provider integrates OpenAI's Codex CLI with aibox containers.
    Codex is a lightweight coding agent that runs in the terminal, providing
    ChatGPT-level reasoning with the ability to execute tasks directly within
    your local repository.

    All authentication is handled by the Codex CLI itself. Configuration is
    persisted in the .codex directory across container restarts.

    Example:
        >>> provider = OpenAIProvider()
        >>> provider.name
        'openai'
        >>> provider.is_installed()
        True
        >>> provider.get_cli_command()
        ['codex']
    """

    @property
    def name(self) -> str:
        """
        Get the provider identifier.

        Returns:
            The string "openai"
        """
        return "openai"

    @property
    def display_name(self) -> str:
        """
        Get the human-readable provider name.

        Returns:
            The string "Codex CLI"
        """
        return "Codex CLI"

    def is_installed(self) -> bool:
        """
        Check if OpenAI CLI is installed.
        """
        try:
            result = subprocess.run(
                ["codex", "--version"],
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

        Codex CLI handles authentication independently, so no environment
        variables need to be passed from the host.

        Returns:
            Empty dictionary (no environment variables needed)
        """
        return {}

    def validate_config(self, config: Config) -> None:
        """
        Validate Codex provider configuration.

        No validation is performed. Codex CLI handles all authentication
        independently via its own config directory (.codex/), which is
        mounted from the host to persist sessions across container restarts.

        Args:
            config: The aibox configuration (not currently used)
        """
        # No validation needed - Codex CLI handles authentication independently

    def get_mount_paths(self) -> list[str]:
        """
        Get all configuration paths for Codex CLI.

        Codex CLI stores configuration in ~/.codex/ directory.

        Returns:
            List containing [".codex"]
        """
        return [".codex"]

    def get_cli_command(self) -> list[str]:
        """
        Get the command to run Codex CLI interactively.

        Returns:
            List containing the command ["codex"]
        """
        return ["codex"]

    def get_required_ports(
        self,
        force_auth_port: bool = False,
        project_storage_dir: str | None = None,
        slot_number: int | None = None,
    ) -> dict[str, int]:
        """
        Get port mappings required for Codex OAuth authentication.

        Codex CLI uses port 1455 for its OAuth callback server during the
        "Sign in with ChatGPT" authentication flow.

        Returns:
            Dictionary mapping container port to host port for OAuth callback.
            - If a Codex session already exists: {}
            - If authentication is required: {'1455/tcp': 1455} to satisfy the fixed callback
              port Codex expects.
            - If force_auth_port is True: always expose 1455 regardless of session state.
        """
        if force_auth_port:
            return {"1455/tcp": 1455}

        if self._has_codex_session(
            project_storage_dir=project_storage_dir, slot_number=slot_number
        ):
            return {}

        return {"1455/tcp": 1455}

    def _has_codex_session(self, project_storage_dir: str | None, slot_number: int | None) -> bool:
        """
        Best-effort check for an existing Codex OAuth session on the host.

        We rely on the slot-scoped ~/.aibox/projects/<project>/slots/<slot>/.codex
        directory. If it exists and contains any non-empty files, assume
        authentication already completed and skip exposing the OAuth port.
        """
        if not project_storage_dir or slot_number is None:
            return False

        codex_dir = (
            Path.home()
            / ".aibox"
            / "projects"
            / project_storage_dir
            / "slots"
            / f"slot-{slot_number}"
            / ".codex"
        )
        if not codex_dir.exists():
            return False

        known_files = [
            codex_dir / "config.json",
            codex_dir / "config",
            codex_dir / "session.json",
        ]

        for file_path in known_files:
            try:
                if file_path.exists() and file_path.stat().st_size > 0:
                    return True
            except OSError:
                continue

        try:
            return any(p.is_file() and p.stat().st_size > 0 for p in codex_dir.iterdir())
        except OSError:
            return False
