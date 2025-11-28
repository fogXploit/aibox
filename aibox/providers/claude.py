"""
Claude AI provider implementation.

This module implements the AIProvider interface for Anthropic's Claude CLI.
It handles:
- Claude CLI installation and detection
- Docker volume mounts for .claude configuration directory

The Claude provider mounts the project's .claude directory to persist
configuration and session state across container restarts. Authentication
is handled entirely by the Claude CLI itself.
"""

import subprocess

from aibox.config.models import Config
from aibox.providers.base import AIProvider


class ClaudeProvider(AIProvider):
    """
    Claude AI provider implementation.

    This provider integrates Anthropic's Claude CLI with aibox containers.
    It mounts the project's .claude directory to persist configuration and
    authentication. All authentication is handled by the Claude CLI itself.

    Example:
        >>> provider = ClaudeProvider()
        >>> provider.name
        'claude'
        >>> provider.is_installed()
        True
        >>> provider.validate_config(config)  # No validation - Claude CLI handles auth
    """

    @property
    def name(self) -> str:
        """
        Get the provider identifier.

        Returns:
            The string "claude"
        """
        return "claude"

    @property
    def display_name(self) -> str:
        """
        Get the human-readable provider name.

        Returns:
            The string "Claude CLI"
        """
        return "Claude CLI"

    def is_installed(self) -> bool:
        """
        Check if Claude CLI is installed and available.

        Runs `claude --version` to verify the CLI is accessible.

        Returns:
            True if Claude CLI is installed and responds to --version,
            False otherwise
        """
        try:
            result = subprocess.run(
                ["claude", "--version"],
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

        Claude CLI handles authentication independently, so no environment
        variables need to be passed from the host.

        Returns:
            Empty dictionary (no environment variables needed)
        """
        return {}

    def validate_config(self, config: Config) -> None:
        """
        Validate Claude provider configuration.

        No validation is performed. Claude CLI handles all authentication
        independently via its own config directory (.claude/), which is
        mounted from the host to persist sessions across container restarts.

        Args:
            config: The aibox configuration (not currently used)
        """
        # No validation needed - Claude CLI handles authentication independently

    def get_mount_paths(self) -> list[str]:
        """
        Get all configuration paths for Claude Code.

        Claude Code stores configuration in:
        - ~/.claude/ directory (session data, projects, settings, etc.)

        `.claude` is mounted directly; `.claude.json` is mirrored into that
        directory by the wrapper script so it persists per slot without
        requiring the file to pre-exist on the host.

        Returns:
            List containing [".claude"]
        """
        return [".claude"]

    def get_cli_command(self) -> list[str]:
        """
        Get the command to run Claude CLI with persistence wrapper.

        Returns a wrapper script that:
        1. Copies .claude.json from slot dir to home on startup (if exists)
        2. Runs Claude CLI normally
        3. Copies .claude.json back to slot dir on exit (if created/modified)

        This ensures .claude.json persistence without Docker bind mount issues.

        Returns:
            List containing wrapper script command
        """
        return [
            "sh",
            "-c",
            """
            mkdir -p ~/.claude

            # Copy .claude.json from slot-scoped mount (if present) to home on startup
            if [ -f ~/.claude/.claude.json ]; then
                cp ~/.claude/.claude.json ~/.claude.json
            fi

            # Run claude CLI (trap ensures cleanup even if interrupted)
            trap 'if [ -f ~/.claude.json ]; then cp ~/.claude.json ~/.claude/.claude.json; fi' EXIT
            claude "$@"
            """,
            "--",  # Separator between script and its arguments
        ]

    def get_required_ports(
        self,
        force_auth_port: bool = False,
        project_storage_dir: str | None = None,
        slot_number: int | None = None,
    ) -> dict[str, tuple[str, int]]:
        """
        Get port mappings required for Claude Code OAuth authentication.
        Nothing needed because Claude creates a link to generage a token which can be easily copy pasted.
        """
        _ = force_auth_port  # Unused; provided for interface compatibility
        _ = project_storage_dir
        _ = slot_number
        return {}
