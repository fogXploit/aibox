"""
Volume mount management for Docker containers.

Handles preparation of volume mounts including standard mounts
(project directory, aibox metadata) and custom mounts from config.
Mounts global provider configuration directories (e.g., ~/.claude/) for
persistence across all slots.
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING

from aibox.config.models import MountConfig

if TYPE_CHECKING:
    from aibox.providers.base import AIProvider


class VolumeManager:
    """Manages Docker volume mounts for aibox containers."""

    def __init__(self, project_dir: str | Path, project_storage_dir: str) -> None:
        """
        Initialize volume manager.

        Args:
            project_dir: Project directory path
            project_storage_dir: Storage directory name (e.g., "myproject-a1b2c3d4")
        """
        self.project_dir = Path(project_dir).resolve()
        self.project_storage_dir = project_storage_dir
        self.aibox_dir = Path.home() / ".aibox" / "projects" / project_storage_dir

    def prepare_volumes(
        self,
        slot_number: int,
        provider: "AIProvider",
        custom_mounts: list[MountConfig] | None = None,
    ) -> dict[str, dict[str, str]]:
        """
        Prepare volume mount dictionary for Docker.

        Creates standard mounts for project directory, slot-specific metadata,
        provider configuration paths (files and directories), and custom mounts.

        Note: Provider config paths (e.g., .claude/, .gemini/, .openai/) are
        isolated per slot, allowing different accounts/API keys per slot.
        Each slot maintains its own provider authentication and session state.

        Args:
            slot_number: Slot number (1-10) for this container
            provider: AI provider instance for mount paths
            custom_mounts: Optional list of custom mounts from config

        Returns:
            Dictionary mapping host paths to mount configuration
            Format: {"/host/path": {"bind": "/container/path", "mode": "rw"}}

        Example:
            >>> vm = VolumeManager("/home/user/project", "a1b2c3d4")
            >>> from aibox.providers.claude import ClaudeProvider
            >>> volumes = vm.prepare_volumes(1, ClaudeProvider())
            >>> volumes["/home/user/project"]
            {"bind": "/workspace", "mode": "rw"}
            >>> # Provider configs are slot-specific
            >>> "/home/user/.aibox/projects/a1b2c3d4/slots/slot-1/.claude" in volumes
            True
        """
        volumes: dict[str, dict[str, str]] = {}

        # Standard mount: project directory → /workspace
        volumes[str(self.project_dir)] = {"bind": "/workspace", "mode": "rw"}

        # Slot-specific directory structure
        slot_dir = self.aibox_dir / "slots" / f"slot-{slot_number}"
        slot_dir.mkdir(parents=True, exist_ok=True)

        # Mount slot-specific provider configuration paths
        # Each slot has its own provider configs for multi-account support
        mount_paths = provider.get_mount_paths()
        for path_name in mount_paths:
            # Use slot-specific path instead of global home directory
            host_path = slot_dir / path_name
            container_path = f"/home/aibox/{path_name}"

            # Create provider config path if it doesn't exist
            if not host_path.exists():
                # Check if path has a file extension (indicates it's a file)
                if host_path.suffix:
                    # Skip files - let AI CLI create them
                    # Files are persisted via wrapper scripts (copy on startup/shutdown)
                    # This avoids Docker bind mount issues (requires file to exist)
                    continue
                else:
                    # Create as directory
                    host_path.mkdir(parents=True, exist_ok=True)

            # Only mount paths that exist
            if not host_path.exists():
                continue

            # Handle directories
            if host_path.is_dir():
                # Ensure directory is writable
                if not os.access(host_path, os.W_OK):
                    try:
                        host_path.chmod(0o755)
                    except OSError:
                        # Skip if we can't change permissions
                        continue

            # Handle files
            elif host_path.is_file() and not os.access(host_path, os.R_OK | os.W_OK):
                # Ensure file is readable/writable
                try:
                    host_path.chmod(0o644)
                except OSError:
                    # Skip if we can't change permissions
                    continue

            # Mount path (Docker SDK handles files and directories the same way)
            volumes[str(host_path)] = {
                "bind": container_path,
                "mode": "rw",
            }

        # Special-case Claude: also mount .claude/.claude.json to ~/.claude.json if present
        if provider.name == "claude":
            claude_json = slot_dir / ".claude" / ".claude.json"
            if claude_json.exists():
                volumes[str(claude_json)] = {
                    "bind": "/home/aibox/.claude.json",
                    "mode": "rw",
                }

        # Custom mounts from configuration
        if custom_mounts:
            for mount in custom_mounts:
                source = Path(mount.source).expanduser().resolve()

                # Ensure source exists for read-only mounts
                # (read-write mounts might be created by container)
                if mount.mode == "ro" and not source.exists():
                    # Skip non-existent read-only mounts with warning
                    # (could add logging here)
                    continue

                volumes[str(source)] = {"bind": mount.target, "mode": mount.mode}

        return volumes

    def get_aibox_dir(self) -> Path:
        """
        Get the aibox metadata directory for this project.

        Returns:
            Path to ~/.aibox/projects/<hash>/
        """
        return self.aibox_dir

    def ensure_directories(self) -> None:
        """Create necessary directories for the project."""
        # Create main aibox directory
        self.aibox_dir.mkdir(parents=True, exist_ok=True)

        # Create slots directory
        (self.aibox_dir / "slots").mkdir(exist_ok=True)
