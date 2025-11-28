"""
Slot management for parallel container instances.

Manages metadata for multiple parallel containers (slots) per project,
allowing users to run different AI providers or configurations simultaneously.
"""

import contextlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from aibox.utils.errors import NoAvailableSlotsError, SlotNotFoundError


class SlotConfig:
    """Configuration and metadata for a single container slot."""

    def __init__(self, project_storage_dir: str, slot_num: int) -> None:
        """
        Initialize slot configuration.

        Args:
            project_storage_dir: Project storage directory name (e.g., "myproject-a1b2c3d4")
            slot_num: Slot number (1-10)
        """
        self.project_storage_dir = project_storage_dir
        self.slot_num = slot_num
        self.slot_dir = (
            Path.home() / ".aibox" / "projects" / project_storage_dir / "slots" / f"slot-{slot_num}"
        )
        self.config_path = self.slot_dir / "metadata.yml"

    def exists(self) -> bool:
        """
        Check if slot configuration exists.

        Returns:
            True if slot is allocated, False otherwise
        """
        return self.config_path.exists()

    def save(self, ai_provider: str, container_name: str) -> None:
        """
        Save slot configuration.

        Args:
            ai_provider: AI provider name (claude, gemini, openai)
            container_name: Docker container name
        """
        # Create slot directory (not just slots parent directory)
        self.slot_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "ai_provider": ai_provider,
            "container_name": container_name,
            "created_at": datetime.now(UTC).isoformat(),
            "last_used": datetime.now(UTC).isoformat(),
        }

        self.config_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def load(self) -> dict[str, Any] | None:
        """
        Load slot configuration.

        Returns:
            Slot configuration dictionary, or None if slot doesn't exist
        """
        if not self.config_path.exists():
            return None

        try:
            data: dict[str, Any] = yaml.safe_load(self.config_path.read_text())
            return data if data else None
        except (yaml.YAMLError, OSError):
            # If file is corrupted, treat as non-existent
            return None

    def get_ai_provider(self) -> str | None:
        """
        Get AI provider for this slot.

        Returns:
            AI provider name, or None if slot doesn't exist
        """
        config = self.load()
        return config.get("ai_provider") if config else None

    def get_container_name(self) -> str | None:
        """
        Get container name for this slot.

        Returns:
            Container name, or None if slot doesn't exist
        """
        config = self.load()
        return config.get("container_name") if config else None

    def update_last_used(self) -> None:
        """Update last used timestamp for this slot."""
        config = self.load()
        if config:
            config["last_used"] = datetime.now(UTC).isoformat()
            self.config_path.write_text(
                yaml.dump(config, default_flow_style=False, sort_keys=False)
            )

    def delete(self) -> None:
        """
        Delete entire slot directory.

        Removes the slot directory including metadata, provider configs,
        and all other slot-specific data.
        """
        import shutil

        if self.slot_dir.exists():
            shutil.rmtree(self.slot_dir)


class SlotManager:
    """Manages all slots for a project."""

    def __init__(self, project_storage_dir: str, max_slots: int = 10) -> None:
        """
        Initialize slot manager.

        Args:
            project_storage_dir: Project storage directory name (e.g., "myproject-a1b2c3d4")
            max_slots: Maximum number of slots (default: 10)
        """
        self.project_storage_dir = project_storage_dir
        self.max_slots = max_slots
        self.slots_dir = Path.home() / ".aibox" / "projects" / project_storage_dir / "slots"

    def find_available_slot(self, start: int = 1) -> int:
        """
        Find next available slot number.

        Args:
            start: Start searching from this slot number (default: 1)

        Returns:
            Available slot number

        Raises:
            NoAvailableSlotsError: If all slots are in use
        """
        for i in range(start, self.max_slots + 1):
            slot_config = SlotConfig(self.project_storage_dir, i)
            if not slot_config.exists():
                return i

        raise NoAvailableSlotsError(
            message=f"No available slots (max: {self.max_slots})",
            suggestion="Stop an existing container to free up a slot, or increase max_slots",
        )

    def get_slot(self, slot_num: int) -> SlotConfig:
        """
        Get slot configuration for a specific slot number.

        Args:
            slot_num: Slot number

        Returns:
            SlotConfig instance

        Raises:
            SlotNotFoundError: If slot number is invalid
        """
        if slot_num < 1:
            raise SlotNotFoundError(
                message=f"Invalid slot number: {slot_num}",
                suggestion="Slot number must be 1 or greater",
            )

        return SlotConfig(self.project_storage_dir, slot_num)

    def list_slots(self) -> list[dict[str, Any]]:
        """
        List all allocated slots for project.

        Returns:
            List of slot dictionaries with slot number and metadata
        """
        if not self.slots_dir.exists():
            return []

        slots: list[dict[str, Any]] = []
        for slot_dir in sorted(self.slots_dir.glob("slot-*")):
            # Only process directories, not files
            if not slot_dir.is_dir():
                continue

            try:
                slot_num = int(slot_dir.name.split("-")[1])
                config = SlotConfig(self.project_storage_dir, slot_num).load()
                if config:
                    slots.append({"slot": slot_num, **config})
            except (ValueError, IndexError):
                # Skip malformed directory names
                continue

        return slots

    def get_next_slot_number(self) -> int:
        """
        Get the next available slot number (sequential).

        Returns:
            Next slot number (1 if no slots exist, otherwise max + 1)

        Raises:
            NoAvailableSlotsError: If max_slots limit reached
        """
        slots = self.list_slots()
        if not slots:
            return 1

        max_slot: int = max(int(slot["slot"]) for slot in slots)
        next_slot = max_slot + 1

        if next_slot > self.max_slots:
            raise NoAvailableSlotsError(
                message=f"Maximum slots ({self.max_slots}) reached",
                suggestion="Clean up unused slots with 'aibox slot cleanup' to free up space",
            )

        return next_slot

    def renumber_slots(self) -> None:
        """
        Renumber slots to be sequential starting from 1.

        After removing slots, this compacts the numbering so there are no gaps.
        For example, slots [1, 3, 5] become [1, 2, 3].

        The container_name field is preserved (not renamed) to keep Docker container references valid.
        Renames entire slot directories including provider configs and metadata.
        """
        import shutil

        slots = self.list_slots()
        if not slots:
            return

        # Sort by slot number
        sorted_slots = sorted(slots, key=lambda s: s["slot"])

        # Renumber sequentially
        for new_slot_num, slot_data in enumerate(sorted_slots, start=1):
            old_slot_num = slot_data["slot"]

            if old_slot_num == new_slot_num:
                # Already in correct position
                continue

            # Get old and new slot directories
            old_slot = SlotConfig(self.project_storage_dir, old_slot_num)
            new_slot = SlotConfig(self.project_storage_dir, new_slot_num)

            # Rename entire slot directory (includes metadata, provider configs, .aibox)
            if old_slot.slot_dir.exists():
                shutil.move(str(old_slot.slot_dir), str(new_slot.slot_dir))

                # Update metadata file with correct timestamps (container_name preserved)
                slot_config_data = new_slot.load()
                if slot_config_data:
                    # Preserve original timestamps
                    slot_config_data["created_at"] = slot_data.get("created_at")
                    slot_config_data["last_used"] = slot_data.get("last_used")
                    new_slot.config_path.write_text(
                        yaml.dump(slot_config_data, default_flow_style=False, sort_keys=False)
                    )

    def cleanup_slot(self, slot_num: int) -> None:
        """
        Clean up and delete a slot.

        Removes the Docker image associated with the slot and deletes the slot metadata.
        Only cleans up if the container is stopped (running containers are skipped).

        Args:
            slot_num: Slot number to clean up
        """
        from aibox.containers.manager import ContainerManager
        from aibox.utils.errors import DockerNotFoundError

        slot_config = self.get_slot(slot_num)
        slot_data = slot_config.load()

        if slot_data:
            # Extract project name and AI provider from slot metadata
            container_name = slot_data.get("container_name", "")
            ai_provider = slot_data.get("ai_provider", "")

            # Extract project name from container name
            # Format: aibox-{project_name}-{slot_number}
            project_name = ""
            if container_name:
                parts = container_name.split("-")
                if len(parts) >= 3 and parts[0] == "aibox":
                    # Join everything except first part (aibox) and last part (slot number)
                    project_name = "-".join(parts[1:-1])

            # Only cleanup if we have required information
            if project_name and ai_provider:
                try:
                    container_manager = ContainerManager()

                    # Check if container is running (Option A: only cleanup stopped containers)
                    if container_name and container_manager.is_container_running(container_name):
                        # Container is still running, skip cleanup
                        return

                    # Remove stopped container belonging to slot
                    if container_name:
                        with contextlib.suppress(Exception):
                            container_manager.remove_container(container_name, force=False)

                    # Remove Docker image for this slot's provider
                    image_repo = f"aibox-{project_name}-{ai_provider}"
                    self._remove_provider_images(container_manager, image_repo=image_repo)
                except DockerNotFoundError:
                    # Docker not available, skip image cleanup
                    pass
                except Exception:
                    # Best effort - don't fail if image removal fails
                    pass

        # Always delete slot metadata
        slot_config.delete()

        # Renumber remaining slots to be sequential
        self.renumber_slots()

    def _remove_provider_images(self, container_manager: Any, image_repo: str) -> None:
        """
        Remove all tags for a provider image when unused by any container.

        Args:
            container_manager: Container manager instance
            image_repo: Image repository prefix (e.g., "aibox-project-claude")
        """
        removed = False

        # Remove all tags for this repo if no container uses them
        images = container_manager.list_images(filters={"reference": f"{image_repo}:*"})
        for image in images or []:
            for tag in getattr(image, "tags", []) or []:
                if not tag.startswith(f"{image_repo}:"):
                    continue

                with contextlib.suppress(Exception):
                    if not container_manager.is_image_in_use(tag):
                        container_manager.remove_image(tag, force=False)
                        removed = True

        # Fallback to latest tag if nothing was removed (e.g., no image list returned)
        if not removed:
            fallback_tag = f"{image_repo}:latest"
            with contextlib.suppress(Exception):
                if not container_manager.is_image_in_use(fallback_tag):
                    container_manager.remove_image(fallback_tag, force=False)

    def cleanup_all_slots(self) -> None:
        """
        Delete all slot configurations and Docker images for this project.

        Removes all provider-specific images (claude, gemini, openai) and deletes
        all slot metadata files. Only cleans up stopped containers.
        """
        from aibox.containers.manager import ContainerManager
        from aibox.utils.errors import DockerNotFoundError

        if not self.slots_dir.exists():
            return

        # Collect all unique providers and project name from slots
        providers: set[str] = set()
        project_name: str = ""
        running_slots: set[int] = set()
        slot_details: list[tuple[int, str, str]] = []

        try:
            container_manager = ContainerManager()
        except DockerNotFoundError:
            # Docker not available, skip image cleanup
            container_manager = None

        # First pass: identify providers and check for running containers
        for slot_dir in self.slots_dir.glob("slot-*"):
            # Only process directories, not files
            if not slot_dir.is_dir():
                continue

            try:
                slot_num = int(slot_dir.name.split("-")[1])
                slot_config = SlotConfig(self.project_storage_dir, slot_num)
                slot_data = slot_config.load()

                if slot_data:
                    ai_provider = slot_data.get("ai_provider", "")
                    if ai_provider:
                        providers.add(ai_provider)

                    container_name = slot_data.get("container_name", "")
                    slot_details.append((slot_num, container_name, ai_provider))

                    # Extract project name from container name
                    if not project_name and container_name:
                        parts = container_name.split("-")
                        if len(parts) >= 3 and parts[0] == "aibox":
                            project_name = "-".join(parts[1:-1])

                    # Check if container is running
                    if (
                        container_manager
                        and container_name
                        and container_manager.is_container_running(container_name)
                    ):
                        running_slots.add(slot_num)
            except (ValueError, IndexError, yaml.YAMLError):
                # Skip malformed directories
                continue

        # Remove stopped containers for slots being cleaned
        if container_manager:
            for slot_num, container_name, _ in slot_details:
                if slot_num in running_slots:
                    continue

                if container_name:
                    try:
                        container_manager.remove_container(container_name, force=False)
                    except Exception:
                        # Best effort - continue cleanup
                        continue

        # Remove Docker images for all providers (only if no containers running)
        if container_manager and project_name and not running_slots:
            for provider in providers:
                try:
                    image_repo = f"aibox-{project_name}-{provider}"
                    self._remove_provider_images(container_manager, image_repo=image_repo)
                except Exception:
                    # Best effort - don't fail if image removal fails
                    pass

        # Delete all slot directories (skip running slots)
        for slot_dir in self.slots_dir.glob("slot-*"):
            # Only process directories, not files
            if not slot_dir.is_dir():
                continue

            try:
                slot_num = int(slot_dir.name.split("-")[1])
                # Skip running slots (Option A: only cleanup stopped)
                if slot_num not in running_slots:
                    slot_config = SlotConfig(self.project_storage_dir, slot_num)
                    slot_config.delete()
            except (ValueError, IndexError):
                # Skip malformed directory names
                continue
