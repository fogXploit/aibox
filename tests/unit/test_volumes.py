"""Unit tests for volume management."""

import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from aibox.config.models import MountConfig
from aibox.containers.volumes import VolumeManager


@pytest.fixture(autouse=True)
def cleanup_test_volumes() -> None:
    """Clean up test volume directories before each test to prevent state leakage."""
    test_dir = Path.home() / ".aibox" / "projects" / "test"
    if not test_dir.exists():
        return

    def _handle_remove_readonly(func, path, _exc_info) -> None:
        """Best-effort permission fixer for stubborn paths created during tests."""
        try:
            Path(path).chmod(0o755)
            func(path)
        except Exception:
            # Ignore if still failing; tests should not abort on cleanup
            pass

    shutil.rmtree(test_dir, onerror=_handle_remove_readonly)


class TestVolumeManager:
    """Tests for VolumeManager class."""

    def test_init(self, tmp_path: Path) -> None:
        """Test volume manager initialization."""
        vm = VolumeManager(tmp_path, "test123")
        assert vm.project_dir == tmp_path.resolve()
        assert vm.project_storage_dir == "test123"
        assert "test123" in str(vm.aibox_dir)

    def test_prepare_volumes_standard_mounts(self, tmp_path: Path) -> None:
        """Test that standard mounts are created with slot-specific provider config."""
        vm = VolumeManager(tmp_path, "test123")

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.get_mount_paths.return_value = [".claude"]

        volumes = vm.prepare_volumes(slot_number=1, provider=mock_provider)

        # Check project directory mount
        assert str(tmp_path.resolve()) in volumes
        assert volumes[str(tmp_path.resolve())] == {"bind": "/workspace", "mode": "rw"}

        # Check slot-specific provider config directory mount (isolated per slot)
        provider_config_dir = vm.aibox_dir / "slots" / "slot-1" / ".claude"
        assert str(provider_config_dir) in volumes
        assert volumes[str(provider_config_dir)] == {"bind": "/home/aibox/.claude", "mode": "rw"}

    def test_prepare_volumes_creates_aibox_dir(self, tmp_path: Path) -> None:
        """Test that slot-specific directories are created."""
        vm = VolumeManager(tmp_path, "test456")

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.get_mount_paths.return_value = [".claude"]

        vm.prepare_volumes(slot_number=2, provider=mock_provider)

        # Check main aibox directory created
        assert vm.aibox_dir.exists()
        assert vm.aibox_dir.is_dir()

        # Check slot directory created
        slot_dir = vm.aibox_dir / "slots" / "slot-2"
        assert slot_dir.exists()
        assert slot_dir.is_dir()

        # Check slot-specific provider config directory created
        provider_dir = slot_dir / ".claude"
        assert provider_dir.exists()
        assert provider_dir.is_dir()

    def test_prepare_volumes_with_custom_mounts(self, tmp_path: Path) -> None:
        """Test custom mounts are included."""
        # Create custom mount sources
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        custom_mounts = [
            MountConfig(source=str(custom_dir), target="/custom", mode="ro"),
            MountConfig(source=str(data_dir), target="/data", mode="rw"),
        ]

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.get_mount_paths.return_value = [".claude"]

        vm = VolumeManager(tmp_path, "test789")
        volumes = vm.prepare_volumes(
            slot_number=1, provider=mock_provider, custom_mounts=custom_mounts
        )

        # Check custom read-only mount
        assert str(custom_dir.resolve()) in volumes
        assert volumes[str(custom_dir.resolve())] == {"bind": "/custom", "mode": "ro"}

        # Check custom read-write mount
        assert str(data_dir.resolve()) in volumes
        assert volumes[str(data_dir.resolve())] == {"bind": "/data", "mode": "rw"}

    def test_prepare_volumes_skips_nonexistent_readonly(self, tmp_path: Path) -> None:
        """Test that non-existent read-only mounts are skipped."""
        custom_mounts = [
            MountConfig(source=str(tmp_path / "missing"), target="/missing", mode="ro")
        ]

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.get_mount_paths.return_value = [".claude"]

        vm = VolumeManager(tmp_path, "test")
        volumes = vm.prepare_volumes(
            slot_number=1, provider=mock_provider, custom_mounts=custom_mounts
        )

        # Non-existent read-only mount should be skipped
        assert str((tmp_path / "missing").resolve()) not in volumes
        # Should still have standard mounts (project + slot metadata + provider config = 2)
        assert len(volumes) == 2

    def test_prepare_volumes_expands_tilde(self, tmp_path: Path) -> None:
        """Test that tilde in paths is expanded."""
        # Create data directory in actual home
        actual_home = Path.home()
        test_data_dir = actual_home / "test_aibox_data"
        test_data_dir.mkdir(exist_ok=True)

        try:
            custom_mounts = [MountConfig(source="~/test_aibox_data", target="/data", mode="ro")]

            # Mock provider
            mock_provider = MagicMock()
            mock_provider.get_mount_paths.return_value = [".claude"]

            vm = VolumeManager(tmp_path, "test")
            volumes = vm.prepare_volumes(
                slot_number=1, provider=mock_provider, custom_mounts=custom_mounts
            )

            # Should expand ~ to home directory
            assert str(test_data_dir.resolve()) in volumes
        finally:
            # Cleanup
            if test_data_dir.exists():
                test_data_dir.rmdir()

    def test_prepare_volumes_empty_custom_mounts(self, tmp_path: Path) -> None:
        """Test with empty custom mounts list."""
        # Mock provider
        mock_provider = MagicMock()
        mock_provider.get_mount_paths.return_value = [".claude"]

        vm = VolumeManager(tmp_path, "test")
        volumes = vm.prepare_volumes(slot_number=1, provider=mock_provider, custom_mounts=[])

        # Should still have standard mounts (project + slot metadata + provider config = 2)
        assert len(volumes) == 2

    def test_get_aibox_dir(self, tmp_path: Path) -> None:
        """Test getting aibox directory."""
        vm = VolumeManager(tmp_path, "abc123")
        aibox_dir = vm.get_aibox_dir()

        assert aibox_dir == Path.home() / ".aibox" / "projects" / "abc123"

    def test_ensure_directories(self, tmp_path: Path) -> None:
        """Test ensuring directories exist."""
        vm = VolumeManager(tmp_path, "xyz789")
        vm.ensure_directories()

        assert vm.aibox_dir.exists()
        assert (vm.aibox_dir / "slots").exists()

    def test_ensure_directories_idempotent(self, tmp_path: Path) -> None:
        """Test that calling ensure_directories multiple times is safe."""
        vm = VolumeManager(tmp_path, "test")
        vm.ensure_directories()
        vm.ensure_directories()  # Should not raise error

        assert vm.aibox_dir.exists()


class TestPerSlotIsolation:
    """Tests for per-slot isolation functionality."""

    def test_different_slots_get_different_directories(self, tmp_path: Path) -> None:
        """Test that different slots get isolated directories."""
        vm = VolumeManager(tmp_path, "test123")

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.get_mount_paths.return_value = [".claude"]

        # Prepare volumes for slot 1
        vm.prepare_volumes(slot_number=1, provider=mock_provider)
        slot1_aibox_dir = vm.aibox_dir / "slots" / "slot-1" / ".aibox"

        # Prepare volumes for slot 5
        vm.prepare_volumes(slot_number=5, provider=mock_provider)
        slot5_aibox_dir = vm.aibox_dir / "slots" / "slot-5" / ".aibox"

        # Verify slot directories exist (metadata managed per slot)
        assert slot1_aibox_dir.parent.exists()
        assert slot5_aibox_dir.parent.exists()

    def test_different_providers_get_different_config_dirs(self, tmp_path: Path) -> None:
        """Test that different providers get different slot-specific config directories."""
        vm = VolumeManager(tmp_path, "test456")

        # Mock Claude provider
        mock_claude = MagicMock()
        mock_claude.get_mount_paths.return_value = [".claude"]

        # Mock Gemini provider
        mock_gemini = MagicMock()
        mock_gemini.get_mount_paths.return_value = [".gemini"]

        # Prepare volumes for Claude (slot 1)
        volumes_claude = vm.prepare_volumes(slot_number=1, provider=mock_claude)

        # Prepare volumes for Gemini (slot 2)
        volumes_gemini = vm.prepare_volumes(slot_number=2, provider=mock_gemini)

        # Verify Claude config directory (slot-specific)
        claude_config_dir = vm.aibox_dir / "slots" / "slot-1" / ".claude"
        assert str(claude_config_dir) in volumes_claude
        assert volumes_claude[str(claude_config_dir)]["bind"] == "/home/aibox/.claude"

        # Verify Gemini config directory (slot-specific)
        gemini_config_dir = vm.aibox_dir / "slots" / "slot-2" / ".gemini"
        assert str(gemini_config_dir) in volumes_gemini
        assert volumes_gemini[str(gemini_config_dir)]["bind"] == "/home/aibox/.gemini"

    def test_slot_metadata_isolated_per_slot(self, tmp_path: Path) -> None:
        """Test that slot metadata directories are isolated."""
        vm = VolumeManager(tmp_path, "test789")

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.get_mount_paths.return_value = [".claude"]

        # Prepare volumes for multiple slots
        vm.prepare_volumes(slot_number=1, provider=mock_provider)
        vm.prepare_volumes(slot_number=2, provider=mock_provider)
        vm.prepare_volumes(slot_number=3, provider=mock_provider)

        # Create test files in each slot directory to verify isolation
        slot1_dir = vm.aibox_dir / "slots" / "slot-1"
        slot2_dir = vm.aibox_dir / "slots" / "slot-2"
        slot3_dir = vm.aibox_dir / "slots" / "slot-3"

        (slot1_dir / "metadata.json").touch()
        (slot2_dir / "metadata.json").touch()
        (slot3_dir / "metadata.json").touch()

        # Verify files exist independently
        assert (slot1_dir / "metadata.json").exists()
        assert (slot2_dir / "metadata.json").exists()
        assert (slot3_dir / "metadata.json").exists()

    def test_provider_config_dir_bind_mount_path(self, tmp_path: Path) -> None:
        """Test that provider config directories bind to correct container paths."""
        vm = VolumeManager(tmp_path, "test")

        # Test Claude (slot 1)
        mock_claude = MagicMock()
        mock_claude.get_mount_paths.return_value = [".claude"]
        volumes_claude = vm.prepare_volumes(slot_number=1, provider=mock_claude)

        # Find the Claude config mount
        claude_mount = None
        for host_path, mount_config in volumes_claude.items():
            if ".claude" in host_path and mount_config["bind"] == "/home/aibox/.claude":
                claude_mount = mount_config
                break
        assert claude_mount is not None
        assert claude_mount["mode"] == "rw"

        # Test OpenAI (different slot)
        mock_openai = MagicMock()
        mock_openai.get_mount_paths.return_value = [".openai"]
        volumes_openai = vm.prepare_volumes(slot_number=2, provider=mock_openai)

        # Find the OpenAI config mount
        openai_mount = None
        for host_path, mount_config in volumes_openai.items():
            if ".openai" in host_path and mount_config["bind"] == "/home/aibox/.openai":
                openai_mount = mount_config
                break
        assert openai_mount is not None
        assert openai_mount["mode"] == "rw"

    def test_all_slots_1_through_10_supported(self, tmp_path: Path) -> None:
        """Test that all slot numbers 1-10 are supported."""
        vm = VolumeManager(tmp_path, "test")

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.get_mount_paths.return_value = [".claude"]

        # Prepare volumes for all slots 1-10
        for slot_num in range(1, 11):
            vm.prepare_volumes(slot_number=slot_num, provider=mock_provider)

            # Verify slot directory created
            slot_dir = vm.aibox_dir / "slots" / f"slot-{slot_num}"
            assert slot_dir.exists()

            # Verify slot-specific provider config directory created
            provider_dir = slot_dir / ".claude"
            assert provider_dir.exists()


class TestProviderConfigPermissions:
    """Tests for provider config permission handling."""

    def test_provider_config_dir_created_if_not_exists(self, tmp_path: Path) -> None:
        """Test that provider config directory is created if it doesn't exist."""
        vm = VolumeManager(tmp_path, "test")

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.get_mount_paths.return_value = [".claude"]

        # Prepare volumes - should create provider config dir
        volumes = vm.prepare_volumes(slot_number=1, provider=mock_provider)

        # Verify provider config directory was created
        provider_dir = vm.aibox_dir / "slots" / "slot-1" / ".claude"
        assert provider_dir.exists()
        assert provider_dir.is_dir()
        assert str(provider_dir) in volumes

    def test_provider_config_dir_with_existing_writable_directory(self, tmp_path: Path) -> None:
        """Test mounting existing writable provider config directory."""
        vm = VolumeManager(tmp_path, "test")

        # Pre-create provider config directory with correct permissions
        slot_dir = vm.aibox_dir / "slots" / "slot-1"
        slot_dir.mkdir(parents=True, exist_ok=True)
        provider_dir = slot_dir / ".claude"
        provider_dir.mkdir(mode=0o755, exist_ok=True)

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.get_mount_paths.return_value = [".claude"]

        # Prepare volumes
        volumes = vm.prepare_volumes(slot_number=1, provider=mock_provider)

        # Verify it's mounted correctly
        assert str(provider_dir) in volumes
        assert volumes[str(provider_dir)]["bind"] == "/home/aibox/.claude"
        assert volumes[str(provider_dir)]["mode"] == "rw"

    def test_provider_config_file_with_existing_readable_file(self, tmp_path: Path) -> None:
        """Test mounting existing readable provider config file."""
        vm = VolumeManager(tmp_path, "test")

        # Pre-create provider config file (use slot 2 to avoid conflicts)
        slot_dir = vm.aibox_dir / "slots" / "slot-2"
        slot_dir.mkdir(parents=True, exist_ok=True)
        config_file = slot_dir / ".claude.json"
        config_file.write_text('{"key": "value"}')
        config_file.chmod(0o644)

        # Mock provider requesting file mount
        mock_provider = MagicMock()
        mock_provider.get_mount_paths.return_value = [".claude.json"]

        # Prepare volumes
        volumes = vm.prepare_volumes(slot_number=2, provider=mock_provider)

        # Verify file is mounted
        assert str(config_file) in volumes
        assert volumes[str(config_file)]["bind"] == "/home/aibox/.claude.json"

    def test_provider_config_handles_permission_errors_gracefully(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that permission errors on chmod are handled gracefully."""
        import os

        vm = VolumeManager(tmp_path, "test")

        # Pre-create slot directory and provider config directory with restricted permissions (use slot 3)
        slot_dir = vm.aibox_dir / "slots" / "slot-3"
        slot_dir.mkdir(parents=True, exist_ok=True)
        provider_dir = slot_dir / ".claude"
        provider_dir.mkdir(mode=0o000, exist_ok=True)  # No permissions

        # Mock os.access to return False (simulating unwritable directory)
        original_access = os.access

        def mock_access(path: str, mode: int) -> bool:
            if "slot-3" in str(path) and ".claude" in str(path) and mode == os.W_OK:
                return False
            return original_access(path, mode)

        monkeypatch.setattr(os, "access", mock_access)

        # Mock chmod to raise OSError
        original_chmod = Path.chmod

        def mock_chmod(self: Path, mode: int) -> None:
            if "slot-3" in str(self) and ".claude" in str(self):
                raise OSError("Permission denied")
            original_chmod(self, mode)

        monkeypatch.setattr(Path, "chmod", mock_chmod)

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.get_mount_paths.return_value = [".claude"]

        # Prepare volumes - should continue despite permission error
        volumes = vm.prepare_volumes(slot_number=3, provider=mock_provider)

        # Directory exists but should not be mounted due to permission issues
        assert provider_dir.exists()
        # The mount should be skipped due to chmod failure
        assert str(provider_dir) not in volumes

    def test_multiple_provider_paths_mounted(self, tmp_path: Path) -> None:
        """Test that multiple provider directory paths are mounted correctly."""
        vm = VolumeManager(tmp_path, "test")

        # Mock provider with multiple mount paths (directories only)
        mock_provider = MagicMock()
        mock_provider.get_mount_paths.return_value = [".claude", ".claude-history"]

        # Prepare volumes
        volumes = vm.prepare_volumes(slot_number=1, provider=mock_provider)

        # Verify directories are created and mounted
        slot_dir = vm.aibox_dir / "slots" / "slot-1"

        claude_dir = slot_dir / ".claude"
        assert claude_dir.exists()
        assert str(claude_dir) in volumes

        history_dir = slot_dir / ".claude-history"
        assert history_dir.exists()
        assert str(history_dir) in volumes

    def test_config_files_not_created_by_aibox(self, tmp_path: Path) -> None:
        """Test that config files are NOT created by aibox (only directories).

        Config files like .claude.json are persisted via wrapper scripts
        (copy on startup/shutdown) rather than Docker bind mounts.
        """
        vm = VolumeManager(tmp_path, "test")

        # Mock provider with directory only (no .claude.json in mount paths)
        mock_provider = MagicMock()
        mock_provider.get_mount_paths.return_value = [".claude"]

        # Prepare volumes
        volumes = vm.prepare_volumes(slot_number=1, provider=mock_provider)

        claude_dir = vm.aibox_dir / "slots" / "slot-1" / ".claude"
        claude_json = vm.aibox_dir / "slots" / "slot-1" / ".claude.json"

        # Verify directory was created
        assert claude_dir.exists()
        assert claude_dir.is_dir()

        # Verify .claude.json was NOT created
        assert not claude_json.exists(), ".claude.json should NOT be created by aibox"

        # Verify directory is mounted
        assert str(claude_dir) in volumes

    def test_files_not_created_only_directories(self, tmp_path: Path) -> None:
        """Test that files with extensions are NOT created (only directories).

        Config files are persisted via wrapper scripts rather than bind mounts.
        """
        vm = VolumeManager(tmp_path, "test")

        # Mock provider with mixed paths
        mock_provider = MagicMock()
        mock_provider.get_mount_paths.return_value = [".config", ".history.txt", ".settings.yaml"]

        # Prepare volumes - should NOT create files, only directories
        volumes = vm.prepare_volumes(slot_number=1, provider=mock_provider)

        slot_dir = vm.aibox_dir / "slots" / "slot-1"
        config_dir = slot_dir / ".config"
        history_file = slot_dir / ".history.txt"
        settings_file = slot_dir / ".settings.yaml"

        # Verify directory was created
        assert config_dir.exists()
        assert config_dir.is_dir()

        # Verify files were NOT created
        assert not history_file.exists(), "Files should NOT be created by aibox"
        assert not settings_file.exists(), "Files should NOT be created by aibox"

        # Verify only directory is mounted, files are not
        assert str(config_dir) in volumes
        assert str(history_file) not in volumes
        assert str(settings_file) not in volumes

    def test_provider_config_directory_permission_handling(self, tmp_path: Path) -> None:
        """Test that read-only provider directories are handled gracefully."""
        vm = VolumeManager(tmp_path, "test")

        # Create slot directory and provider config directory with restricted permissions
        slot_dir = vm.aibox_dir / "slots" / "slot-1"
        slot_dir.mkdir(parents=True, exist_ok=True)

        provider_dir = slot_dir / ".claude"
        provider_dir.mkdir(parents=True, exist_ok=True)

        # Try to set read-only permissions (might not work in all environments)
        try:
            provider_dir.chmod(0o555)
        except (OSError, PermissionError):
            pytest.skip("Cannot set directory permissions in this environment")

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.get_mount_paths.return_value = [".claude"]

        # Prepare volumes - should handle read-only directories without crashing
        volumes = vm.prepare_volumes(slot_number=1, provider=mock_provider)

        # Verify directory is still mounted even if permissions couldn't be fixed
        assert str(provider_dir) in volumes
        assert provider_dir.exists()

    def test_provider_config_file_permission_handling(self, tmp_path: Path) -> None:
        """Test that read-only provider config files are handled gracefully."""
        vm = VolumeManager(tmp_path, "test")

        # Create slot directory and provider config file with restricted permissions
        slot_dir = vm.aibox_dir / "slots" / "slot-1"
        slot_dir.mkdir(parents=True, exist_ok=True)

        config_file = slot_dir / ".claude.json"
        config_file.write_text("{}")

        # Try to set read-only permissions (might not work in all environments)
        try:
            config_file.chmod(0o444)
        except (OSError, PermissionError):
            pytest.skip("Cannot set file permissions in this environment")

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.get_mount_paths.return_value = [".claude.json"]

        # Prepare volumes - should handle read-only files without crashing
        volumes = vm.prepare_volumes(slot_number=1, provider=mock_provider)

        # Verify file is still mounted even if permissions couldn't be fixed
        assert str(config_file) in volumes
        assert config_file.exists()
