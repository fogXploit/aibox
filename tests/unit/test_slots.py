"""Unit tests for slot management."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from aibox.containers.slot import SlotConfig, SlotManager
from aibox.utils.errors import NoAvailableSlotsError, SlotNotFoundError


class TestSlotConfig:
    """Tests for SlotConfig class."""

    def test_init(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test slot config initialization."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        slot = SlotConfig("proj123", 1)
        assert slot.project_storage_dir == "proj123"
        assert slot.slot_num == 1
        assert "proj123" in str(slot.config_path)
        assert "slot-1" in str(slot.slot_dir)
        assert "metadata.yml" in str(slot.config_path)

    def test_exists_false_initially(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that slot doesn't exist initially."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        slot = SlotConfig("test", 1)
        assert not slot.exists()

    def test_save_and_load(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test saving and loading slot configuration."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        slot = SlotConfig("test", 1)
        slot.save("claude", "aibox-myproject-1")

        assert slot.exists()

        config = slot.load()
        assert config is not None
        assert config["ai_provider"] == "claude"
        assert config["container_name"] == "aibox-myproject-1"
        assert "created_at" in config
        assert "last_used" in config

    def test_load_nonexistent_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test loading non-existent slot returns None."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        slot = SlotConfig("test", 1)
        assert slot.load() is None

    def test_get_ai_provider(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting AI provider from slot."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        slot = SlotConfig("test", 1)
        slot.save("gemini", "aibox-test-1")

        assert slot.get_ai_provider() == "gemini"

    def test_get_ai_provider_none_when_not_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting AI provider returns None for non-existent slot."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        slot = SlotConfig("test", 1)
        assert slot.get_ai_provider() is None

    def test_get_container_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting container name from slot."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        slot = SlotConfig("test", 2)
        slot.save("claude", "aibox-myproject-2")

        assert slot.get_container_name() == "aibox-myproject-2"

    def test_get_container_name_none_when_not_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting container name returns None for non-existent slot."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        slot = SlotConfig("test", 1)
        assert slot.get_container_name() is None

    def test_update_last_used(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test updating last used timestamp."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        slot = SlotConfig("test", 1)
        slot.save("claude", "aibox-test-1")

        config1 = slot.load()
        assert config1 is not None
        original_time = config1["last_used"]

        # Update last used
        slot.update_last_used()

        config2 = slot.load()
        assert config2 is not None
        new_time = config2["last_used"]

        # Time should be updated (or equal if very fast)
        assert new_time >= original_time

    def test_update_last_used_no_effect_if_not_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test updating last used on non-existent slot has no effect."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        slot = SlotConfig("test", 1)
        slot.update_last_used()  # Should not raise error
        assert not slot.exists()

    def test_delete(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test deleting slot configuration."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        slot = SlotConfig("test", 1)
        slot.save("claude", "aibox-test-1")
        assert slot.exists()

        slot.delete()
        assert not slot.exists()

    def test_delete_nonexistent_no_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test deleting non-existent slot doesn't raise error."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        slot = SlotConfig("test", 1)
        slot.delete()  # Should not raise error

    def test_load_corrupted_file_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test loading corrupted YAML file returns None."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        slot = SlotConfig("test", 1)
        # Create slot directory (not just parent)
        slot.slot_dir.mkdir(parents=True, exist_ok=True)
        # Invalid YAML with unclosed bracket
        slot.config_path.write_text("key: [invalid\n  - missing bracket")

        assert slot.load() is None


class TestSlotManager:
    """Tests for SlotManager class."""

    def test_init(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test slot manager initialization."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        manager = SlotManager("proj123", max_slots=5)
        assert manager.project_storage_dir == "proj123"
        assert manager.max_slots == 5

    def test_find_available_slot_when_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test finding available slot when all are free."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        manager = SlotManager("test")
        slot_num = manager.find_available_slot()
        assert slot_num == 1

    def test_find_available_slot_with_start(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test finding available slot starting from specific number."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        manager = SlotManager("test")
        slot_num = manager.find_available_slot(start=5)
        assert slot_num == 5

    def test_find_available_slot_skips_occupied(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test finding available slot skips occupied slots."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Occupy slots 1, 2, 3
        for i in range(1, 4):
            slot = SlotConfig("test", i)
            slot.save("claude", f"aibox-test-{i}")

        manager = SlotManager("test")
        slot_num = manager.find_available_slot()
        assert slot_num == 4

    def test_find_available_slot_raises_when_full(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that finding slot raises error when all are occupied."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        manager = SlotManager("test", max_slots=3)

        # Occupy all slots
        for i in range(1, 4):
            slot = SlotConfig("test", i)
            slot.save("claude", f"aibox-test-{i}")

        with pytest.raises(NoAvailableSlotsError):
            manager.find_available_slot()

    def test_get_slot(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting slot configuration."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        manager = SlotManager("test")
        slot = manager.get_slot(5)
        assert slot.slot_num == 5
        assert slot.project_storage_dir == "test"

    def test_get_slot_invalid_number_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting invalid slot number raises error."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        manager = SlotManager("test", max_slots=20)

        # Only slot numbers < 1 are invalid (no upper bound)
        with pytest.raises(SlotNotFoundError):
            manager.get_slot(0)

        with pytest.raises(SlotNotFoundError):
            manager.get_slot(-1)

    def test_list_slots_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test listing slots when none exist."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        manager = SlotManager("test")
        slots = manager.list_slots()
        assert slots == []

    def test_list_slots_with_data(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test listing slots with data."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create some slots
        slot1 = SlotConfig("test", 1)
        slot1.save("claude", "aibox-test-1")

        slot3 = SlotConfig("test", 3)
        slot3.save("gemini", "aibox-test-3")

        manager = SlotManager("test")
        slots = manager.list_slots()

        assert len(slots) == 2
        assert slots[0]["slot"] == 1
        assert slots[0]["ai_provider"] == "claude"
        assert slots[1]["slot"] == 3
        assert slots[1]["ai_provider"] == "gemini"

    def test_cleanup_slot(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test cleaning up a slot."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        slot = SlotConfig("test", 1)
        slot.save("claude", "aibox-test-1")

        manager = SlotManager("test")
        manager.cleanup_slot(1)

        assert not slot.exists()

    def test_cleanup_all_slots(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test cleaning up all slots."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create multiple slots
        for i in range(1, 4):
            slot = SlotConfig("test", i)
            slot.save("claude", f"aibox-test-{i}")

        manager = SlotManager("test")
        manager.cleanup_all_slots()

        # All slots should be gone
        assert manager.list_slots() == []

    def test_cleanup_all_slots_when_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test cleaning up all slots when none exist."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        manager = SlotManager("test")
        manager.cleanup_all_slots()  # Should not raise error
        assert manager.list_slots() == []

    @patch("aibox.containers.manager.ContainerManager")
    def test_cleanup_slot_removes_image(
        self, mock_container_mgr: Mock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that cleanup_slot removes Docker image."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create slot with metadata
        slot = SlotConfig("test-project", 1)
        slot.save(
            ai_provider="claude",
            container_name="aibox-myproject-1",
        )

        # Mock ContainerManager
        mock_mgr_instance = mock_container_mgr.return_value
        mock_mgr_instance.is_container_running.return_value = False
        mock_mgr_instance.is_image_in_use.return_value = False
        mock_mgr_instance.list_images.return_value = [
            SimpleNamespace(tags=["aibox-myproject-claude:latest", "aibox-myproject-claude:abc123"])
        ]

        # Cleanup slot
        manager = SlotManager("test-project")
        manager.cleanup_slot(1)

        # Verify container was removed first
        mock_mgr_instance.remove_container.assert_called_once_with(
            "aibox-myproject-1", force=False
        )
        # Verify image was removed
        removed_images = {call.args[0] for call in mock_mgr_instance.remove_image.call_args_list}
        assert removed_images == {
            "aibox-myproject-claude:latest",
            "aibox-myproject-claude:abc123",
        }
        assert not slot.exists()

    @patch("aibox.containers.manager.ContainerManager")
    def test_cleanup_slot_removes_container_and_image_when_unused(
        self, mock_container_mgr: Mock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Remove container and image when slot container is stopped and image unused elsewhere."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        slot = SlotConfig("test-project", 1)
        slot.save(
            ai_provider="claude",
            container_name="aibox-myproject-1",
        )

        mock_mgr_instance = mock_container_mgr.return_value
        mock_mgr_instance.is_container_running.return_value = False
        mock_mgr_instance.is_image_in_use.return_value = False
        mock_mgr_instance.list_images.return_value = [
            SimpleNamespace(tags=["aibox-myproject-claude:latest"])
        ]

        manager = SlotManager("test-project")
        manager.cleanup_slot(1)

        mock_mgr_instance.remove_container.assert_called_once_with(
            "aibox-myproject-1", force=False
        )
        mock_mgr_instance.remove_image.assert_called_once_with(
            "aibox-myproject-claude:latest", force=False
        )
        assert not slot.exists()

    @patch("aibox.containers.manager.ContainerManager")
    def test_cleanup_slot_skips_running_container(
        self, mock_container_mgr: Mock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that cleanup_slot skips cleanup if container is running."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create slot with metadata
        slot = SlotConfig("test-project", 1)
        slot.save(
            ai_provider="claude",
            container_name="aibox-myproject-1",
        )

        # Mock ContainerManager - container is running
        mock_mgr_instance = mock_container_mgr.return_value
        mock_mgr_instance.is_container_running.return_value = True
        mock_mgr_instance.is_image_in_use.return_value = False
        mock_mgr_instance.list_images.return_value = []

        # Cleanup slot
        manager = SlotManager("test-project")
        manager.cleanup_slot(1)

        # Verify image was NOT removed (container still running)
        mock_mgr_instance.remove_image.assert_not_called()
        mock_mgr_instance.remove_container.assert_not_called()
        mock_mgr_instance.list_images.assert_not_called()
        # Slot metadata should still exist
        assert slot.exists()

    @patch("aibox.containers.manager.ContainerManager")
    def test_cleanup_all_slots_removes_all_images(
        self, mock_container_mgr: Mock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that cleanup_all_slots removes all provider images."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create slots with different providers
        slot1 = SlotConfig("test-project", 1)
        slot1.save(
            ai_provider="claude",
            container_name="aibox-myproject-1",
        )

        slot2 = SlotConfig("test-project", 2)
        slot2.save(
            ai_provider="gemini",
            container_name="aibox-myproject-2",
        )

        slot3 = SlotConfig("test-project", 3)
        slot3.save(
            ai_provider="openai",
            container_name="aibox-myproject-3",
        )

        # Mock ContainerManager - no containers running
        mock_mgr_instance = mock_container_mgr.return_value
        mock_mgr_instance.is_container_running.return_value = False
        mock_mgr_instance.is_image_in_use.return_value = False
        image_map = {
            "aibox-myproject-claude:*": ["aibox-myproject-claude:latest", "aibox-myproject-claude:abc"],
            "aibox-myproject-gemini:*": ["aibox-myproject-gemini:latest"],
            "aibox-myproject-openai:*": ["aibox-myproject-openai:latest"],
        }

        def list_images_side_effect(filters: dict | None = None) -> list:
            reference = (filters or {}).get("reference", "")
            tags = image_map.get(reference, [])
            return [SimpleNamespace(tags=tags)] if tags else []

        mock_mgr_instance.list_images.side_effect = list_images_side_effect

        # Cleanup all slots
        manager = SlotManager("test-project")
        manager.cleanup_all_slots()

        # Verify containers were removed
        assert mock_mgr_instance.remove_container.call_count == 3
        removed_containers = {call[0][0] for call in mock_mgr_instance.remove_container.call_args_list}
        assert removed_containers == {
            "aibox-myproject-1",
            "aibox-myproject-2",
            "aibox-myproject-3",
        }

        # Verify all provider images were removed
        assert mock_mgr_instance.remove_image.call_count == 4
        removed_images = {call[0][0] for call in mock_mgr_instance.remove_image.call_args_list}
        assert removed_images == {
            "aibox-myproject-claude:latest",
            "aibox-myproject-claude:abc",
            "aibox-myproject-gemini:latest",
            "aibox-myproject-openai:latest",
        }

        # All slots should be cleaned up
        assert manager.list_slots() == []

    @patch("aibox.containers.manager.ContainerManager")
    def test_cleanup_all_slots_skips_running_containers(
        self, mock_container_mgr: Mock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that cleanup_all_slots skips slots with running containers."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create two slots
        slot1 = SlotConfig("test-project", 1)
        slot1.save(
            ai_provider="claude",
            container_name="aibox-myproject-1",
        )

        slot2 = SlotConfig("test-project", 2)
        slot2.save(
            ai_provider="gemini",
            container_name="aibox-myproject-2",
        )

        # Mock ContainerManager - slot 1 is running, slot 2 is stopped
        mock_mgr_instance = mock_container_mgr.return_value

        def is_running_side_effect(name: str) -> bool:
            return name == "aibox-myproject-1"

        mock_mgr_instance.is_container_running.side_effect = is_running_side_effect
        mock_mgr_instance.is_image_in_use.return_value = False
        mock_mgr_instance.list_images.return_value = []

        # Cleanup all slots
        manager = SlotManager("test-project")
        manager.cleanup_all_slots()

        # Verify NO images were removed (at least one container running)
        mock_mgr_instance.remove_image.assert_not_called()
        # Only stopped slot should have its container removed
        mock_mgr_instance.remove_container.assert_called_once_with(
            "aibox-myproject-2", force=False
        )
        mock_mgr_instance.list_images.assert_not_called()

        # Slot 1 should still exist (running), slot 2 should be cleaned up
        slots = manager.list_slots()
        assert len(slots) == 1
        assert slots[0]["slot"] == 1

    def test_get_next_slot_number_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting next slot number when no slots exist."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        manager = SlotManager("test")
        next_slot = manager.get_next_slot_number()
        assert next_slot == 1

    def test_get_next_slot_number_sequential(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting next slot number with existing sequential slots."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create slots 1, 2, 3
        for i in range(1, 4):
            slot = SlotConfig("test", i)
            slot.save("claude", f"aibox-test-{i}")

        manager = SlotManager("test")
        next_slot = manager.get_next_slot_number()
        assert next_slot == 4

    def test_get_next_slot_number_with_gaps(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting next slot number with gaps in numbering."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create slots 1, 3, 5 (gaps at 2, 4)
        for i in [1, 3, 5]:
            slot = SlotConfig("test", i)
            slot.save("claude", f"aibox-test-{i}")

        manager = SlotManager("test")
        next_slot = manager.get_next_slot_number()
        # Should return max + 1 = 6
        assert next_slot == 6

    def test_get_next_slot_number_max_reached(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test error when maximum slots reached."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        manager = SlotManager("test", max_slots=3)

        # Fill all slots
        for i in range(1, 4):
            slot = SlotConfig("test", i)
            slot.save("claude", f"aibox-test-{i}")

        with pytest.raises(NoAvailableSlotsError) as exc_info:
            manager.get_next_slot_number()

        assert "Maximum slots (3) reached" in str(exc_info.value)

    def test_renumber_slots_no_gaps(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test renumbering with no gaps (should be no-op)."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create sequential slots 1, 2, 3
        for i in range(1, 4):
            slot = SlotConfig("test", i)
            slot.save("claude", f"aibox-test-{i}")

        manager = SlotManager("test")
        manager.renumber_slots()

        # Slots should remain the same
        slots = manager.list_slots()
        assert len(slots) == 3
        assert [s["slot"] for s in slots] == [1, 2, 3]
        assert [s["container_name"] for s in slots] == [
            "aibox-test-1",
            "aibox-test-2",
            "aibox-test-3",
        ]

    def test_renumber_slots_with_gaps(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test renumbering compacts gaps in slot numbers."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create slots 1, 3, 5 (gaps at 2, 4)
        slot1 = SlotConfig("test", 1)
        slot1.save("claude", "aibox-test-1")

        slot3 = SlotConfig("test", 3)
        slot3.save("gemini", "aibox-test-3")

        slot5 = SlotConfig("test", 5)
        slot5.save("openai", "aibox-test-5")

        manager = SlotManager("test")
        manager.renumber_slots()

        # Should be renumbered to 1, 2, 3
        slots = manager.list_slots()
        assert len(slots) == 3
        assert [s["slot"] for s in slots] == [1, 2, 3]

        # Container names should be preserved
        assert slots[0]["container_name"] == "aibox-test-1"
        assert slots[0]["ai_provider"] == "claude"

        assert slots[1]["container_name"] == "aibox-test-3"  # Was slot 3, now slot 2
        assert slots[1]["ai_provider"] == "gemini"

        assert slots[2]["container_name"] == "aibox-test-5"  # Was slot 5, now slot 3
        assert slots[2]["ai_provider"] == "openai"

    def test_renumber_slots_preserves_timestamps(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that renumbering preserves created_at and last_used timestamps."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create slot 3 with specific timestamps
        slot3 = SlotConfig("test", 3)
        slot3.save("claude", "aibox-test-3")

        # Manually set timestamps
        import time

        time.sleep(0.1)  # Small delay to ensure different timestamp
        original_data = slot3.load()
        assert original_data is not None
        original_created = original_data["created_at"]
        original_used = original_data["last_used"]

        # Wait a bit and renumber
        time.sleep(0.1)
        manager = SlotManager("test")
        manager.renumber_slots()

        # Slot 3 should now be slot 1
        slot1 = SlotConfig("test", 1)
        new_data = slot1.load()
        assert new_data is not None

        # Timestamps should be preserved
        assert new_data["created_at"] == original_created
        assert new_data["last_used"] == original_used
        assert new_data["container_name"] == "aibox-test-3"

    def test_renumber_slots_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test renumbering with no slots (should be no-op)."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        manager = SlotManager("test")
        manager.renumber_slots()  # Should not raise error

        slots = manager.list_slots()
        assert len(slots) == 0

    @patch("aibox.containers.manager.ContainerManager")
    def test_cleanup_slot_triggers_renumbering(
        self, mock_container_mgr: Mock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that cleanup_slot triggers renumbering of remaining slots."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create slots 1, 2, 3
        for i in range(1, 4):
            slot = SlotConfig("test-project", i)
            slot.save(
                ai_provider="claude",
                container_name=f"aibox-test-{i}",
            )

        # Mock ContainerManager - no containers running
        mock_mgr_instance = mock_container_mgr.return_value
        mock_mgr_instance.is_container_running.return_value = False
        mock_mgr_instance.is_image_in_use.return_value = False

        # Cleanup slot 2
        manager = SlotManager("test-project")
        manager.cleanup_slot(2)

        # Should now have slots 1, 2 (was 1, 3)
        slots = manager.list_slots()
        assert len(slots) == 2
        assert [s["slot"] for s in slots] == [1, 2]

        # Verify slot 2 now contains what was slot 3
        slot2 = SlotConfig("test-project", 2)
        slot2_data = slot2.load()
        assert slot2_data is not None
        assert slot2_data["container_name"] == "aibox-test-3"
