"""Unit tests for config commands."""

from unittest.mock import MagicMock, Mock, patch

import pytest
from rich.console import Console

from aibox.cli.commands.config import config_edit, config_show, config_validate
from aibox.config.models import (
    Config,
    DockerConfig,
    DockerResourceConfig,
    GlobalConfig,
    MountConfig,
    ProjectConfig,
)
from aibox.utils.errors import ConfigNotFoundError, SlotNotFoundError


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


@pytest.fixture
def sample_config():
    """Create sample config for testing."""
    return Config(
        global_config=GlobalConfig(
            version="1.0",
            docker=DockerConfig(
                base_image="debian:bookworm-slim",
                default_resources=DockerResourceConfig(
                    cpus=2,
                    memory="4g",
                ),
            ),
        ),
        project=ProjectConfig(
            name="test-project",
            profiles=["python:3.12"],
            mounts=[
                MountConfig(source="/host/data", target="/data", mode="ro"),
            ],
            environment={"MY_VAR": "value"},
        ),
    )


class TestConfigShow:
    """Tests for config_show command."""

    @patch("aibox.cli.commands.config.SlotManager")
    @patch("aibox.cli.commands.config.get_project_storage_dir")
    @patch("aibox.cli.commands.config.load_config")
    @patch("aibox.cli.commands.config.console")
    def test_config_show_success_with_default_slot(
        self,
        mock_console,
        mock_load_config,
        mock_get_storage_dir,
        mock_slot_manager_cls,
        temp_project_root,
        sample_config,
    ):
        """Test config_show displays configuration with default slot 1."""
        # Setup
        mock_load_config.return_value = sample_config
        mock_get_storage_dir.return_value = "test-project-abc123"

        mock_slot_manager = Mock()
        mock_slot_manager_cls.return_value = mock_slot_manager

        mock_slot_config = Mock()
        mock_slot_config.load.return_value = {
            "ai_provider": "claude",
            "container_name": "aibox-test-1",
            "created_at": "2025-01-15T10:30:00Z",
            "last_used": "2025-01-15T12:45:00Z",
        }
        mock_slot_manager.get_slot.return_value = mock_slot_config

        # Execute
        config_show(temp_project_root, slot_number=1)

        # Verify
        mock_load_config.assert_called_once_with(str(temp_project_root))
        mock_slot_manager.get_slot.assert_called_once_with(1)
        mock_console.print.assert_called()

    @patch("aibox.cli.commands.config.SlotManager")
    @patch("aibox.cli.commands.config.get_project_storage_dir")
    @patch("aibox.cli.commands.config.load_config")
    @patch("aibox.cli.commands.config.console")
    def test_config_show_success_with_specific_slot(
        self,
        mock_console,
        mock_load_config,
        mock_get_storage_dir,
        mock_slot_manager_cls,
        temp_project_root,
        sample_config,
    ):
        """Test config_show displays configuration for specific slot."""
        # Setup
        mock_load_config.return_value = sample_config
        mock_get_storage_dir.return_value = "test-project-abc123"

        mock_slot_manager = Mock()
        mock_slot_manager_cls.return_value = mock_slot_manager

        mock_slot_config = Mock()
        mock_slot_config.load.return_value = {
            "ai_provider": "gemini",
            "container_name": "aibox-test-3",
            "created_at": "2025-01-15T11:00:00Z",
            "last_used": "2025-01-15T13:00:00Z",
        }
        mock_slot_manager.get_slot.return_value = mock_slot_config

        # Execute
        config_show(temp_project_root, slot_number=3)

        # Verify
        mock_slot_manager.get_slot.assert_called_once_with(3)
        mock_console.print.assert_called()

    @patch("aibox.cli.commands.config.SlotManager")
    @patch("aibox.cli.commands.config.get_project_storage_dir")
    @patch("aibox.cli.commands.config.load_config")
    @patch("aibox.cli.commands.config.console")
    def test_config_show_slot_not_found(
        self,
        _mock_console,
        mock_load_config,
        mock_get_storage_dir,
        mock_slot_manager_cls,
        temp_project_root,
        sample_config,
    ):
        """Test config_show raises SlotNotFoundError when slot doesn't exist."""
        # Setup
        mock_load_config.return_value = sample_config
        mock_get_storage_dir.return_value = "test-project-abc123"

        mock_slot_manager = Mock()
        mock_slot_manager_cls.return_value = mock_slot_manager

        mock_slot_config = Mock()
        mock_slot_config.load.return_value = None  # Slot doesn't exist
        mock_slot_manager.get_slot.return_value = mock_slot_config

        # Execute and verify
        with pytest.raises(SlotNotFoundError) as exc_info:
            config_show(temp_project_root, slot_number=5)

        assert "Slot 5 not found" in str(exc_info.value)

    @patch("aibox.cli.commands.config.load_config")
    @patch("aibox.cli.commands.config.console")
    def test_config_show_handles_errors(self, mock_console, mock_load_config, temp_project_root):
        """Test config_show handles errors gracefully."""
        # Setup
        mock_load_config.side_effect = Exception("Failed to load")

        # Execute and verify
        with pytest.raises(Exception, match="Failed to load"):
            config_show(temp_project_root)

        mock_console.print.assert_called()


class TestConfigValidate:
    """Tests for config_validate command."""

    @patch("aibox.cli.commands.config.load_config")
    @patch("aibox.cli.commands.config.console")
    def test_config_validate_success(
        self, mock_console, mock_load_config, temp_project_root, sample_config
    ):
        """Test config_validate with valid configuration."""
        # Setup
        mock_load_config.return_value = sample_config

        # Execute
        config_validate(temp_project_root)

        # Verify
        mock_load_config.assert_called_once_with(str(temp_project_root))
        mock_console.print.assert_any_call("[bold green]✓[/bold green] Configuration is valid!\n")

    @patch("aibox.cli.commands.config.load_config")
    @patch("aibox.cli.commands.config.console")
    def test_config_validate_invalid(self, mock_console, mock_load_config, temp_project_root):
        """Test config_validate with invalid configuration."""
        # Setup
        mock_load_config.side_effect = Exception("Invalid configuration")

        # Execute and verify
        with pytest.raises(SystemExit):
            config_validate(temp_project_root)

        mock_console.print.assert_any_call("\n[bold red]✗[/bold red] Configuration is invalid\n")


class TestConfigEdit:
    """Tests for config_edit command."""

    @patch("aibox.cli.commands.config.get_project_config_path")
    @patch("aibox.cli.commands.config.load_config")
    @patch("aibox.cli.commands.config.subprocess.run")
    @patch("aibox.cli.commands.config.os.environ", {"EDITOR": "vim"})
    @patch("aibox.cli.commands.config.console")
    def test_config_edit_success(
        self,
        mock_console,
        mock_subprocess,
        mock_load_config,
        mock_get_config_path,
        temp_project_root,
        sample_config,
        tmp_path,
    ):
        """Test config_edit opens editor and validates successfully."""
        # Setup centralized config path
        config_path = tmp_path / "config.yml"
        config_path.write_text("name: test-project\n")
        mock_get_config_path.return_value = config_path

        mock_subprocess.return_value = MagicMock(returncode=0)
        mock_load_config.return_value = sample_config

        # Execute
        config_edit(temp_project_root)

        # Verify
        mock_subprocess.assert_called_once_with(["vim", str(config_path)], check=False)
        mock_load_config.assert_called_once_with(str(temp_project_root))
        mock_console.print.assert_any_call("[bold green]✓[/bold green] Configuration is valid!\n")

    @patch("aibox.cli.commands.config.console")
    def test_config_edit_no_project_config(self, _mock_console, temp_project_root):
        """Test config_edit raises error when project is not initialized."""
        # Execute and verify
        with pytest.raises(ConfigNotFoundError) as exc_info:
            config_edit(temp_project_root)

        assert "No project configuration found" in str(exc_info.value)

    @patch("aibox.cli.commands.config.get_project_config_path")
    @patch("aibox.cli.commands.config.load_config")
    @patch("aibox.cli.commands.config.subprocess.run")
    @patch("aibox.cli.commands.config.os.environ", {})
    @patch("aibox.cli.commands.config.console")
    def test_config_edit_default_editor(
        self,
        _mock_console,
        mock_subprocess,
        mock_load_config,
        mock_get_config_path,
        temp_project_root,
        sample_config,
        tmp_path,
    ):
        """Test config_edit uses nano as default editor."""
        # Setup centralized config path
        config_path = tmp_path / "config.yml"
        config_path.write_text("name: test-project\n")
        mock_get_config_path.return_value = config_path

        mock_subprocess.return_value = MagicMock(returncode=0)
        mock_load_config.return_value = sample_config

        # Execute
        config_edit(temp_project_root)

        # Verify nano is used as default
        mock_subprocess.assert_called_once_with(["nano", str(config_path)], check=False)

    @patch("aibox.cli.commands.config.get_project_config_path")
    @patch("aibox.cli.commands.config.load_config")
    @patch("aibox.cli.commands.config.subprocess.run")
    @patch("aibox.cli.commands.config.os.environ", {"VISUAL": "emacs"})
    @patch("aibox.cli.commands.config.console")
    def test_config_edit_uses_visual_env(
        self,
        _mock_console,
        mock_subprocess,
        mock_load_config,
        mock_get_config_path,
        temp_project_root,
        sample_config,
        tmp_path,
    ):
        """Test config_edit uses VISUAL environment variable."""
        # Setup centralized config path
        config_path = tmp_path / "config.yml"
        config_path.write_text("name: test-project\n")
        mock_get_config_path.return_value = config_path

        mock_subprocess.return_value = MagicMock(returncode=0)
        mock_load_config.return_value = sample_config

        # Execute
        config_edit(temp_project_root)

        # Verify emacs is used from VISUAL
        mock_subprocess.assert_called_once_with(["emacs", str(config_path)], check=False)

    @patch("aibox.cli.commands.config.get_project_config_path")
    @patch("aibox.cli.commands.config.subprocess.run")
    @patch("aibox.cli.commands.config.os.environ", {"EDITOR": "nonexistent-editor"})
    @patch("aibox.cli.commands.config.console")
    def test_config_edit_editor_not_found(
        self, mock_console, mock_subprocess, mock_get_config_path, temp_project_root, tmp_path
    ):
        """Test config_edit handles missing editor gracefully."""
        # Setup centralized config path
        config_path = tmp_path / "config.yml"
        config_path.write_text("name: test-project\n")
        mock_get_config_path.return_value = config_path

        mock_subprocess.side_effect = FileNotFoundError("Editor not found")

        # Execute and verify
        with pytest.raises(SystemExit):
            config_edit(temp_project_root)

        mock_console.print.assert_any_call(
            "\n[red]Error:[/red] Editor 'nonexistent-editor' not found\n"
        )

    @patch("aibox.cli.commands.config.get_project_config_path")
    @patch("aibox.cli.commands.config.load_config")
    @patch("aibox.cli.commands.config.Confirm.ask")
    @patch("aibox.cli.commands.config.subprocess.run")
    @patch("aibox.cli.commands.config.os.environ", {"EDITOR": "vim"})
    @patch("aibox.cli.commands.config.console")
    def test_config_edit_validation_failure_retry(
        self,
        mock_console,
        mock_subprocess,
        mock_confirm,
        mock_load_config,
        mock_get_config_path,
        temp_project_root,
        sample_config,
        tmp_path,
    ):
        """Test config_edit allows re-editing after validation failure."""
        # Setup centralized config path
        config_path = tmp_path / "config.yml"
        config_path.write_text("name: test-project\n")
        mock_get_config_path.return_value = config_path

        mock_subprocess.return_value = MagicMock(returncode=0)
        # First validation fails, second succeeds
        mock_load_config.side_effect = [Exception("Invalid config"), sample_config]
        mock_confirm.return_value = True  # User wants to retry

        # Execute
        config_edit(temp_project_root)

        # Verify
        assert mock_subprocess.call_count == 2  # Editor opened twice
        assert mock_load_config.call_count == 2  # Validated twice
        mock_console.print.assert_any_call("[bold red]✗[/bold red] Configuration is invalid\n")
        mock_console.print.assert_any_call("[bold green]✓[/bold green] Configuration is valid!\n")

    @patch("aibox.cli.commands.config.get_project_config_path")
    @patch("aibox.cli.commands.config.load_config")
    @patch("aibox.cli.commands.config.Confirm.ask")
    @patch("aibox.cli.commands.config.subprocess.run")
    @patch("aibox.cli.commands.config.os.environ", {"EDITOR": "vim"})
    @patch("aibox.cli.commands.config.console")
    def test_config_edit_validation_failure_abort(
        self,
        mock_console,
        mock_subprocess,
        mock_confirm,
        mock_load_config,
        mock_get_config_path,
        temp_project_root,
        tmp_path,
    ):
        """Test config_edit aborts when user declines retry."""
        # Setup centralized config path
        config_path = tmp_path / "config.yml"
        config_path.write_text("name: test-project\n")
        mock_get_config_path.return_value = config_path

        mock_subprocess.return_value = MagicMock(returncode=0)
        mock_load_config.side_effect = Exception("Invalid config")
        mock_confirm.return_value = False  # User declines retry

        # Execute and verify
        with pytest.raises(SystemExit):
            config_edit(temp_project_root)

        mock_console.print.assert_any_call("\n[yellow]Aborted[/yellow]\n")

    @patch("aibox.cli.commands.config.get_project_config_path")
    @patch("aibox.cli.commands.config.load_config")
    @patch("aibox.cli.commands.config.subprocess.run")
    @patch("aibox.cli.commands.config.os.environ", {"EDITOR": "vim"})
    @patch("aibox.cli.commands.config.console")
    def test_config_edit_keyboard_interrupt(
        self,
        mock_console,
        mock_subprocess,
        _mock_load_config,
        mock_get_config_path,
        temp_project_root,
        tmp_path,
    ):
        """Test config_edit handles keyboard interrupt gracefully."""
        # Setup centralized config path
        config_path = tmp_path / "config.yml"
        config_path.write_text("name: test-project\n")
        mock_get_config_path.return_value = config_path

        mock_subprocess.side_effect = KeyboardInterrupt()

        # Execute and verify
        with pytest.raises(SystemExit) as exc_info:
            config_edit(temp_project_root)

        assert exc_info.value.code == 130
        mock_console.print.assert_any_call("\n\n[yellow]Aborted by user[/yellow]\n")
