"""Unit tests for slot commands."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest
from rich.console import Console

from aibox.cli.commands.slot import (
    _ensure_gemini_session,
    _ensure_openai_session,
    slot_add,
    slot_cleanup,
    slot_list,
)


@pytest.fixture
def mock_console():
    """Mock Rich console."""
    return MagicMock(spec=Console)


@pytest.fixture
def temp_project_root(tmp_path):
    """Create temporary project root."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    return project_root


class TestSlotList:
    """Tests for slot_list command."""

    @patch("aibox.cli.commands.slot.get_project_storage_dir")
    @patch("aibox.cli.commands.slot.ContainerManager")
    @patch("aibox.cli.commands.slot.SlotManager")
    @patch("aibox.cli.commands.slot.console")
    def test_slot_list_with_running_containers(
        self,
        mock_console,
        mock_slot_manager_class,
        mock_container_manager_class,
        mock_storage_dir,
        temp_project_root,
    ):
        """Test slot_list displays running containers correctly."""
        # Setup
        mock_storage_dir.return_value = "test-project-abc12345"
        mock_slot_manager = MagicMock()
        mock_slot_manager_class.return_value = mock_slot_manager
        mock_slot_manager.list_slots.return_value = [
            {"slot": 1, "container_name": "aibox-project-1", "ai_provider": "claude"},
            {"slot": 3, "container_name": "aibox-project-3", "ai_provider": "gemini"},
        ]

        # Mock container manager to report containers as running
        mock_container_manager = MagicMock()
        mock_container_manager_class.return_value = mock_container_manager
        mock_container_manager.is_container_running.return_value = True

        # Execute
        slot_list(temp_project_root)

        # Verify
        mock_storage_dir.assert_called_once_with(temp_project_root)
        mock_slot_manager_class.assert_called_once_with("test-project-abc12345")
        mock_slot_manager.list_slots.assert_called_once()
        mock_container_manager.is_container_running.assert_called()
        mock_console.print.assert_called()

    @patch("aibox.cli.commands.slot.get_project_storage_dir")
    @patch("aibox.cli.commands.slot.ContainerManager")
    @patch("aibox.cli.commands.slot.SlotManager")
    @patch("aibox.cli.commands.slot.console")
    def test_slot_list_with_stopped_containers(
        self,
        mock_console,
        mock_slot_manager_class,
        mock_container_manager_class,
        mock_storage_dir,
        temp_project_root,
    ):
        """Test slot_list displays stopped containers correctly."""
        # Setup
        mock_storage_dir.return_value = "test-project-abc12345"
        mock_slot_manager = MagicMock()
        mock_slot_manager_class.return_value = mock_slot_manager
        mock_slot_manager.list_slots.return_value = [
            {"slot": 1, "container_name": "aibox-project-1", "ai_provider": "claude"},
        ]

        # Mock container manager to report container as stopped
        mock_container_manager = MagicMock()
        mock_container_manager_class.return_value = mock_container_manager
        mock_container_manager.is_container_running.return_value = False

        # Execute
        slot_list(temp_project_root)

        # Verify
        mock_container_manager.is_container_running.assert_called_with("aibox-project-1")
        mock_console.print.assert_called()

    @patch("aibox.cli.commands.slot.get_project_storage_dir")
    @patch("aibox.cli.commands.slot.ContainerManager")
    @patch("aibox.cli.commands.slot.SlotManager")
    @patch("aibox.cli.commands.slot.console")
    def test_slot_list_docker_unavailable(
        self,
        mock_console,
        mock_slot_manager_class,
        mock_container_manager_class,
        mock_storage_dir,
        temp_project_root,
    ):
        """Test slot_list falls back gracefully when Docker is unavailable."""
        from aibox.utils.errors import DockerNotFoundError

        # Setup
        mock_storage_dir.return_value = "test-project-abc12345"
        mock_slot_manager = MagicMock()
        mock_slot_manager_class.return_value = mock_slot_manager
        mock_slot_manager.list_slots.return_value = [
            {"slot": 1, "container_name": "aibox-project-1", "ai_provider": "claude"},
        ]

        # Mock container manager to raise DockerNotFoundError
        mock_container_manager_class.side_effect = DockerNotFoundError("Docker not found")

        # Execute
        slot_list(temp_project_root)

        # Verify - should still show slots with metadata
        mock_console.print.assert_called()

    @patch("aibox.cli.commands.slot.get_project_storage_dir")
    @patch("aibox.cli.commands.slot.SlotManager")
    @patch("aibox.cli.commands.slot.console")
    def test_slot_list_with_slots(
        self, mock_console, mock_slot_manager_class, mock_storage_dir, temp_project_root
    ):
        """Test slot_list displays active slots."""
        # Setup
        mock_storage_dir.return_value = "test-project-abc12345"
        mock_slot_manager = MagicMock()
        mock_slot_manager_class.return_value = mock_slot_manager
        mock_slot_manager.list_slots.return_value = [
            {"slot": 1, "container_name": "aibox-project-1", "ai_provider": "claude"},
            {"slot": 3, "container_name": "aibox-project-3", "ai_provider": "gemini"},
        ]

        # Execute
        slot_list(temp_project_root)

        # Verify
        mock_storage_dir.assert_called_once_with(temp_project_root)
        mock_slot_manager_class.assert_called_once_with("test-project-abc12345")
        mock_slot_manager.list_slots.assert_called_once()
        mock_console.print.assert_called()

    @patch("aibox.cli.commands.slot.SlotManager")
    @patch("aibox.cli.commands.slot.console")
    def test_slot_list_empty(self, mock_console, mock_slot_manager_class, temp_project_root):
        """Test slot_list with no active slots."""
        # Setup
        mock_slot_manager = MagicMock()
        mock_slot_manager_class.return_value = mock_slot_manager
        mock_slot_manager.list_slots.return_value = {}

        # Execute
        slot_list(temp_project_root)

        # Verify
        mock_console.print.assert_any_call("\n[yellow]No active slots[/yellow]\n")

    @patch("aibox.cli.commands.slot.SlotManager")
    @patch("aibox.cli.commands.slot.console")
    def test_slot_list_handles_errors(
        self, _mock_console, mock_slot_manager_class, temp_project_root
    ):
        """Test slot_list handles errors gracefully."""
        # Setup
        mock_slot_manager = MagicMock()
        mock_slot_manager_class.return_value = mock_slot_manager
        mock_slot_manager.list_slots.side_effect = Exception("Failed to list")

        # Execute and verify
        with pytest.raises(Exception, match="Failed to list"):
            slot_list(temp_project_root)


class TestSlotCleanup:
    """Tests for slot_cleanup command."""


class TestSlotAdd:
    """Tests for slot_add command."""

    @patch("aibox.cli.commands.slot._ensure_gemini_session")
    @patch("aibox.cli.commands.slot._select_provider")
    @patch("aibox.cli.commands.slot.ProviderRegistry")
    @patch("aibox.cli.commands.slot.get_project_storage_dir")
    @patch("aibox.cli.commands.slot.SlotManager")
    @patch("aibox.cli.commands.slot.load_project_config")
    @patch("aibox.cli.commands.slot.console")
    @patch("aibox.cli.commands.slot.IntPrompt")
    def test_slot_add_triggers_gemini_login(
        self,
        mock_intprompt,
        _mock_console,
        mock_load_project_config,
        mock_slot_manager_class,
        mock_storage_dir,
        mock_provider_registry,
        mock_select_provider,
        mock_gemini_login,
        temp_project_root,
    ):
        """Ensure Gemini login helper runs when configuring Gemini slot."""
        mock_load_project_config.return_value = MagicMock(
            project=MagicMock(name="test-project", mounts=[])
        )
        mock_storage_dir.return_value = "proj-123"
        mock_slot_manager = MagicMock()
        mock_slot_manager_class.return_value = mock_slot_manager
        mock_slot_manager.list_slots.return_value = []
        mock_slot_manager.get_slot.return_value = MagicMock(save=MagicMock())

        mock_intprompt.ask.return_value = 1
        mock_select_provider.return_value = "gemini"
        mock_provider_registry.list_providers.return_value = ["gemini"]
        mock_provider = MagicMock()
        mock_provider_registry.get_provider.return_value = mock_provider

        slot_add(temp_project_root)

        mock_gemini_login.assert_called_once_with(temp_project_root, 1)

    @patch("aibox.cli.commands.slot._ensure_openai_session")
    @patch("aibox.cli.commands.slot._select_provider")
    @patch("aibox.cli.commands.slot.ProviderRegistry")
    @patch("aibox.cli.commands.slot.get_project_storage_dir")
    @patch("aibox.cli.commands.slot.SlotManager")
    @patch("aibox.cli.commands.slot.load_project_config")
    @patch("aibox.cli.commands.slot.console")
    @patch("aibox.cli.commands.slot.IntPrompt")
    def test_slot_add_triggers_openai_login(
        self,
        mock_intprompt,
        _mock_console,
        mock_load_project_config,
        mock_slot_manager_class,
        mock_storage_dir,
        mock_provider_registry,
        mock_select_provider,
        mock_openai_login,
        temp_project_root,
    ):
        """Ensure OpenAI login helper runs when configuring OpenAI slot."""
        mock_load_project_config.return_value = MagicMock(
            project=MagicMock(name="test-project", mounts=[])
        )
        mock_storage_dir.return_value = "proj-123"
        mock_slot_manager = MagicMock()
        mock_slot_manager_class.return_value = mock_slot_manager
        mock_slot_manager.list_slots.return_value = []
        mock_slot_manager.get_slot.return_value = MagicMock(save=MagicMock())

        mock_intprompt.ask.return_value = 1
        mock_select_provider.return_value = "openai"
        mock_provider_registry.list_providers.return_value = ["openai"]
        mock_provider = MagicMock()
        mock_provider_registry.get_provider.return_value = mock_provider

        slot_add(temp_project_root)

        mock_openai_login.assert_called_once_with(temp_project_root, 1)

    @patch.dict("os.environ", {"GEMINI_API_KEY": "should-not-skip"}, clear=True)
    @patch("aibox.cli.commands.slot.VolumeManager")
    @patch("aibox.cli.commands.slot.ContainerManager")
    @patch("aibox.cli.commands.slot.load_config")
    @patch("aibox.cli.commands.slot.ProviderRegistry.get_provider")
    @patch("aibox.cli.commands.slot.get_project_storage_dir")
    def test_ensure_gemini_session_runs_login_even_with_api_key(
        self,
        mock_storage_dir,
        mock_get_provider,
        mock_load_config,
        mock_container_manager,
        mock_volume_manager,
        temp_project_root,
        tmp_path,
    ):
        """Ensure login helper still runs when API key env vars are set."""
        mock_storage_dir.return_value = "proj-123"

        mock_provider = MagicMock()
        mock_provider.name = "gemini"
        mock_provider.get_docker_env_vars.return_value = {}
        mock_provider.get_mount_paths.return_value = [".gemini"]
        mock_get_provider.return_value = mock_provider

        config = MagicMock()
        config.project = MagicMock(name="projname", profiles=[], mounts=[])
        config.global_config = MagicMock(docker=MagicMock(base_image="debian"))
        mock_load_config.return_value = config

        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_container_manager_obj = MagicMock(
            image_exists=MagicMock(return_value=True),
            create_container=MagicMock(return_value=mock_container),
            tag_image=MagicMock(),
        )
        mock_container_manager.return_value = mock_container_manager_obj

        mock_volume_manager.return_value.prepare_volumes.return_value = {
            "/host": {"bind": "/container", "mode": "rw"}
        }

        # Use isolated home so test doesn't touch real ~/.aibox
        with patch.object(Path, "home", return_value=tmp_path):
            _ensure_gemini_session(temp_project_root, slot_number=1)

        mock_container_manager.assert_called_once()
        mock_container_manager_obj.create_container.assert_called_once()
        mock_container.wait.assert_called_once()

    @patch("aibox.cli.commands.slot.console")
    @patch("aibox.cli.commands.slot.VolumeManager")
    @patch("aibox.cli.commands.slot.ContainerManager")
    @patch("aibox.cli.commands.slot.load_config")
    @patch("aibox.cli.commands.slot.ProviderRegistry.get_provider")
    @patch("aibox.cli.commands.slot.get_project_storage_dir")
    def test_ensure_gemini_session_streams_chunks_on_same_line(
        self,
        mock_storage_dir,
        mock_get_provider,
        mock_load_config,
        mock_container_manager,
        mock_volume_manager,
        mock_console,
        temp_project_root,
        tmp_path,
    ):
        """Stream Gemini login output without inserting newlines per chunk."""
        mock_storage_dir.return_value = "proj-123"

        mock_provider = MagicMock()
        mock_provider.name = "gemini"
        mock_provider.get_docker_env_vars.return_value = {}
        mock_provider.get_mount_paths.return_value = [".gemini"]
        mock_get_provider.return_value = mock_provider

        config = MagicMock()
        config.project = MagicMock(name="projname", profiles=[], mounts=[])
        config.global_config = MagicMock(docker=MagicMock(base_image="debian"))
        mock_load_config.return_value = config

        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_container.logs.return_value = iter([b"h", b"t", b"t", b"p", b"://", b"example.com"])

        mock_container_manager_obj = MagicMock(
            image_exists=MagicMock(return_value=True),
            create_container=MagicMock(return_value=mock_container),
        )
        mock_container_manager.return_value = mock_container_manager_obj

        mock_volume_manager.return_value.prepare_volumes.return_value = {
            "/host": {"bind": "/container", "mode": "rw"}
        }

        with patch.object(Path, "home", return_value=tmp_path):
            _ensure_gemini_session(temp_project_root, slot_number=1)

        for chunk in ["h", "t", "t", "p", "://", "example.com"]:
            mock_console.print.assert_any_call(chunk, end="")

    @patch("aibox.cli.commands.slot.ContainerManager")
    @patch("aibox.cli.commands.slot.get_project_storage_dir")
    def test_ensure_gemini_session_skips_when_session_exists(
        self,
        mock_storage_dir,
        mock_container_manager,
        temp_project_root,
        tmp_path,
    ):
        """Skip login if a non-empty .gemini file already exists."""
        mock_storage_dir.return_value = "proj-123"

        slot_dir = tmp_path / ".aibox" / "projects" / "proj-123" / "slots" / "slot-1"
        gemini_dir = slot_dir / ".gemini"
        gemini_dir.mkdir(parents=True, exist_ok=True)
        session_file = gemini_dir / "session.json"
        session_file.write_text("{}")

        with patch.object(Path, "home", return_value=tmp_path):
            _ensure_gemini_session(temp_project_root, slot_number=1)

        mock_container_manager.assert_not_called()

    @patch("aibox.cli.commands.slot.ContainerManager")
    @patch("aibox.cli.commands.slot.VolumeManager")
    @patch("aibox.cli.commands.slot.load_config")
    @patch("aibox.cli.commands.slot.ProviderRegistry.get_provider")
    @patch("aibox.cli.commands.slot.get_project_storage_dir")
    def test_ensure_openai_session_runs_login_when_missing(
        self,
        mock_storage_dir,
        mock_get_provider,
        mock_load_config,
        mock_volume_manager,
        mock_container_manager,
        temp_project_root,
        tmp_path,
    ):
        """Run OpenAI login helper when no Codex session exists."""
        mock_storage_dir.return_value = "proj-123"

        provider = MagicMock()
        provider.name = "openai"
        provider.get_docker_env_vars.return_value = {}
        provider.get_mount_paths.return_value = [".codex"]
        mock_get_provider.return_value = provider

        config = MagicMock()
        config.project = MagicMock(name="projname", profiles=[], mounts=[])
        config.global_config = MagicMock(docker=MagicMock(base_image="debian"))
        mock_load_config.return_value = config

        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_container_manager_obj = MagicMock(
            image_exists=MagicMock(return_value=True),
            create_container=MagicMock(return_value=mock_container),
            tag_image=MagicMock(),
        )
        mock_container_manager.return_value = mock_container_manager_obj

        mock_volume_manager.return_value.prepare_volumes.return_value = {
            "/host": {"bind": "/container", "mode": "rw"}
        }

        with patch.object(Path, "home", return_value=tmp_path):
            _ensure_openai_session(temp_project_root, slot_number=1)

        mock_container_manager.assert_called_once()
        mock_container_manager_obj.create_container.assert_called_once()
        mock_container.wait.assert_called_once()

    @patch("aibox.cli.commands.slot.console")
    @patch("aibox.cli.commands.slot.ContainerManager")
    @patch("aibox.cli.commands.slot.VolumeManager")
    @patch("aibox.cli.commands.slot.load_config")
    @patch("aibox.cli.commands.slot.ProviderRegistry.get_provider")
    @patch("aibox.cli.commands.slot.get_project_storage_dir")
    def test_ensure_openai_session_streams_chunks_on_same_line(
        self,
        mock_storage_dir,
        mock_get_provider,
        mock_load_config,
        mock_volume_manager,
        mock_container_manager,
        temp_project_root,
        tmp_path,
    ):
        """Stream OpenAI login output without inserting newlines per chunk."""
        mock_storage_dir.return_value = "proj-123"

        provider = MagicMock()
        provider.name = "openai"
        provider.get_docker_env_vars.return_value = {}
        provider.get_mount_paths.return_value = [".codex"]
        provider.get_required_ports.return_value = {"1455/tcp": 1455}
        mock_get_provider.return_value = provider

        config = MagicMock()
        config.project = MagicMock(name="projname", profiles=[], mounts=[])
        config.global_config = MagicMock(docker=MagicMock(base_image="debian"))
        mock_load_config.return_value = config

        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_container.logs.return_value = iter([b"h", b"t", b"t", b"p", b"://", b"example.com"])

        mock_container_manager_obj = MagicMock(
            image_exists=MagicMock(return_value=True),
            create_container=MagicMock(return_value=mock_container),
            tag_image=MagicMock(),
        )
        mock_container_manager.return_value = mock_container_manager_obj

        mock_volume_manager.return_value.prepare_volumes.return_value = {
            "/host": {"bind": "/container", "mode": "rw"}
        }

        mock_buffer = MagicMock()
        mock_stdout = SimpleNamespace(buffer=mock_buffer, write=MagicMock(), flush=MagicMock())

        with patch.object(Path, "home", return_value=tmp_path), patch("sys.stdout", mock_stdout):
            _ensure_openai_session(temp_project_root, slot_number=1)

        expected_chunks = [b"h", b"t", b"t", b"p", b"://", b"example.com"]
        mock_buffer.write.assert_has_calls([call(chunk) for chunk in expected_chunks])

    @patch("aibox.cli.commands.slot.ContainerManager")
    @patch("aibox.cli.commands.slot.get_project_storage_dir")
    def test_ensure_openai_session_skips_when_session_exists(
        self,
        mock_storage_dir,
        mock_container_manager,
        temp_project_root,
        tmp_path,
    ):
        """Skip OpenAI login if slot-scoped Codex config already exists."""
        mock_storage_dir.return_value = "proj-123"

        slot_dir = tmp_path / ".aibox" / "projects" / "proj-123" / "slots" / "slot-1"
        codex_dir = slot_dir / ".codex"
        codex_dir.mkdir(parents=True, exist_ok=True)
        session_file = codex_dir / "config.json"
        session_file.write_text("{}")

        with patch.object(Path, "home", return_value=tmp_path):
            _ensure_openai_session(temp_project_root, slot_number=1)

        mock_container_manager.assert_not_called()

    @patch("aibox.cli.commands.slot.SlotManager")
    @patch("aibox.cli.commands.slot.console")
    def test_slot_cleanup_all_success(
        self, mock_console, mock_slot_manager_class, temp_project_root
    ):
        """Test slot_cleanup cleans up all slots successfully."""
        # Setup
        mock_slot_manager = MagicMock()
        mock_slot_manager_class.return_value = mock_slot_manager

        # Execute - cleanup all slots
        slot_cleanup(temp_project_root, slot_number=None)

        # Verify
        mock_slot_manager.cleanup_all_slots.assert_called_once()
        mock_console.print.assert_any_call(
            "\n[bold blue]Cleaning up all stopped containers...[/bold blue]\n"
        )
        mock_console.print.assert_any_call(
            "[bold green]✓[/bold green] All slots cleaned up successfully\n"
        )

    @patch("aibox.cli.commands.slot.SlotManager")
    @patch("aibox.cli.commands.slot.console")
    def test_slot_cleanup_single_success(
        self, mock_console, mock_slot_manager_class, temp_project_root
    ):
        """Test slot_cleanup cleans up single slot successfully."""
        # Setup
        mock_slot_manager = MagicMock()
        mock_slot_manager_class.return_value = mock_slot_manager

        # Execute - cleanup single slot
        slot_cleanup(temp_project_root, slot_number=2)

        # Verify
        mock_slot_manager.cleanup_slot.assert_called_once_with(2)
        mock_console.print.assert_any_call("\n[bold blue]Cleaning up slot 2...[/bold blue]\n")
        mock_console.print.assert_any_call(
            "[bold green]✓[/bold green] Slot 2 cleaned up successfully\n"
        )

    @patch("aibox.cli.commands.slot.SlotManager")
    @patch("aibox.cli.commands.slot.console")
    def test_slot_cleanup_keyboard_interrupt(
        self, mock_console, mock_slot_manager_class, temp_project_root
    ):
        """Test slot_cleanup handles keyboard interrupt."""
        # Setup
        mock_slot_manager = MagicMock()
        mock_slot_manager_class.return_value = mock_slot_manager
        mock_slot_manager.cleanup_all_slots.side_effect = KeyboardInterrupt()

        # Execute and verify
        with pytest.raises(SystemExit):
            slot_cleanup(temp_project_root)

        mock_console.print.assert_any_call("\n\n[yellow]⚠[/yellow]  Cancelled by user\n")

    @patch("aibox.cli.commands.slot.SlotManager")
    @patch("aibox.cli.commands.slot.console")
    def test_slot_cleanup_handles_errors(
        self, _mock_console, mock_slot_manager_class, temp_project_root
    ):
        """Test slot_cleanup handles errors gracefully."""
        # Setup
        mock_slot_manager = MagicMock()
        mock_slot_manager_class.return_value = mock_slot_manager
        mock_slot_manager.cleanup_all_slots.side_effect = Exception("Failed to cleanup")

        # Execute and verify
        with pytest.raises(Exception, match="Failed to cleanup"):
            slot_cleanup(temp_project_root)
