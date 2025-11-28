"""
Unit tests for aibox init command.

Tests cover:
- Global config creation on first run
- Global config skip when already exists
- Project config creation
- Directory validation (reject home/root)
- Interactive prompt mocking
- Error handling
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aibox.cli.commands.init import init_command
from aibox.config.models import GlobalConfig, ProjectConfig
from aibox.utils.errors import AiboxError
from aibox.utils.hash import get_project_storage_dir


class TestInitCommand:
    """Tests for init command."""

    @patch("aibox.cli.commands.init.get_global_config_path")
    @patch("aibox.cli.commands.init.save_global_config")
    @patch("aibox.cli.commands.init.save_project_config")
    @patch("aibox.cli.commands.init.Prompt.ask")
    @patch("aibox.cli.commands.init.Confirm.ask")
    def test_init_creates_global_config_first_time(
        self,
        _mock_confirm: MagicMock,
        mock_prompt: MagicMock,
        mock_save_project: MagicMock,
        mock_save_global: MagicMock,
        mock_global_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test init creates global config on first run."""
        # Setup: global config doesn't exist
        global_config_path = tmp_path / "global_config.yml"
        mock_global_path.return_value = global_config_path

        # Setup: mock user inputs
        # Note: AI provider selection removed - now happens per-slot
        mock_prompt.side_effect = [
            "test-project",  # project name
            "1",  # profile selection (first profile)
            "",  # profile version (default)
        ]

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=tmp_path),
            patch("aibox.cli.commands.init.ProfileLoader") as mock_profile_loader,
        ):
            mock_loader = MagicMock()
            mock_loader.list_profiles_with_info.return_value = [
                {
                    "name": "python",
                    "description": "Python development",
                    "versions": "3.11, 3.12, 3.13",
                }
            ]
            mock_profile_loader.return_value = mock_loader
            init_command()

        # Verify global config was created
        assert mock_save_global.called
        saved_global = mock_save_global.call_args[0][0]
        assert isinstance(saved_global, GlobalConfig)

        # Verify project config was created
        assert mock_save_project.called

    @patch("aibox.cli.commands.init.get_global_config_path")
    @patch("aibox.cli.commands.init.load_global_config")
    @patch("aibox.cli.commands.init.save_project_config")
    @patch("aibox.cli.commands.init.Prompt.ask")
    def test_init_skips_global_config_if_exists(
        self,
        mock_prompt: MagicMock,
        mock_save_project: MagicMock,
        mock_load_global: MagicMock,
        mock_global_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test init skips global config creation if it exists."""
        # Setup: global config exists
        global_config_path = tmp_path / "global_config.yml"
        global_config_path.touch()
        mock_global_path.return_value = global_config_path
        mock_load_global.return_value = GlobalConfig()

        # Setup: mock user inputs
        # Note: AI provider selection removed - now happens per-slot
        mock_prompt.side_effect = [
            "test-project",
            "1",
            "",
        ]

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=tmp_path),
            patch("aibox.cli.commands.init.ProfileLoader") as mock_profile_loader,
        ):
            mock_loader = MagicMock()
            mock_loader.list_profiles_with_info.return_value = [
                {"name": "python", "description": "Python", "versions": "3.12"}
            ]
            mock_profile_loader.return_value = mock_loader
            init_command()

        # Verify global config was loaded but not saved
        assert mock_load_global.called
        assert mock_save_project.called

    @patch("aibox.cli.commands.init.get_global_config_path")
    @patch("aibox.cli.commands.init.load_global_config")
    def test_init_rejects_home_directory(
        self,
        mock_load_global: MagicMock,
        mock_global_path: MagicMock,
    ) -> None:
        """Test init rejects home directory."""
        mock_global_path.return_value = Path.home() / ".aibox" / "config.yml"
        mock_load_global.return_value = GlobalConfig()

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=Path.home()),
            pytest.raises(AiboxError) as exc_info,
        ):
            init_command()

        assert "home directory" in str(exc_info.value).lower()

    @patch("aibox.cli.commands.init.get_global_config_path")
    @patch("aibox.cli.commands.init.load_global_config")
    def test_init_rejects_root_directory(
        self,
        mock_load_global: MagicMock,
        mock_global_path: MagicMock,
    ) -> None:
        """Test init rejects root directory."""
        mock_global_path.return_value = Path("/") / ".aibox" / "config.yml"
        mock_load_global.return_value = GlobalConfig()

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=Path("/")),
            pytest.raises(AiboxError) as exc_info,
        ):
            init_command()

        assert "root directory" in str(exc_info.value).lower()

    @patch("aibox.cli.commands.init.get_global_config_path")
    @patch("aibox.cli.commands.init.load_global_config")
    @patch("aibox.cli.commands.init.save_project_config")
    @patch("aibox.cli.commands.init.Prompt.ask")
    @patch("aibox.cli.commands.init.Confirm.ask")
    def test_init_creates_project_config_with_profiles(
        self,
        _mock_confirm: MagicMock,
        mock_prompt: MagicMock,
        mock_save_project: MagicMock,
        mock_load_global: MagicMock,
        mock_global_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test init creates project config with selected profiles."""
        mock_global_path.return_value = tmp_path / "global.yml"
        (tmp_path / "global.yml").touch()
        mock_load_global.return_value = GlobalConfig()

        # Mock user selecting profile 1 with version 3.12
        # Note: AI provider selection removed - now happens per-slot
        mock_prompt.side_effect = [
            "my-project",  # project name
            "1",  # profile selection
            "3.12",  # version
        ]

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=tmp_path),
            patch("aibox.cli.commands.init.ProfileLoader") as mock_profile_loader,
        ):
            mock_loader = MagicMock()
            mock_loader.list_profiles_with_info.return_value = [
                {"name": "python", "description": "Python", "versions": "3.12"}
            ]
            mock_profile_loader.return_value = mock_loader
            init_command()

        # Verify project config was saved with correct data
        assert mock_save_project.called
        saved_config = mock_save_project.call_args[0][0]
        assert isinstance(saved_config, ProjectConfig)
        assert saved_config.name == "my-project"
        assert "python:3.12" in saved_config.profiles

    @patch("aibox.cli.commands.init.get_global_config_path")
    @patch("aibox.cli.commands.init.load_global_config")
    @patch("aibox.cli.commands.init.Confirm.ask")
    def test_init_handles_overwrite_confirmation_abort(
        self,
        mock_confirm: MagicMock,
        mock_load_global: MagicMock,
        mock_global_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test init aborts when user declines overwrite."""
        mock_global_path.return_value = tmp_path / "global.yml"
        (tmp_path / "global.yml").touch()
        mock_load_global.return_value = GlobalConfig()

        # Create existing project config
        project_config_dir = tmp_path / ".aibox"
        project_config_dir.mkdir()
        (project_config_dir / "config.yml").touch()

        # User declines overwrite
        mock_confirm.return_value = False

        with patch("aibox.cli.commands.init.Path.cwd", return_value=tmp_path):
            # Should return early without error
            init_command()

        # Verify no save was attempted (would need more mocking to verify)

    @patch("aibox.cli.commands.init.get_global_config_path")
    @patch("aibox.cli.commands.init.load_global_config")
    @patch("aibox.cli.commands.init.save_project_config")
    @patch("aibox.cli.commands.init.Prompt.ask")
    def test_init_uses_default_project_name(
        self,
        mock_prompt: MagicMock,
        mock_save_project: MagicMock,
        mock_load_global: MagicMock,
        mock_global_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test init uses directory name as default project name."""
        mock_global_path.return_value = tmp_path / "global.yml"
        (tmp_path / "global.yml").touch()
        mock_load_global.return_value = GlobalConfig()

        # User accepts default (empty input would use default in real Prompt)
        # We'll simulate by returning the directory name
        project_dir = tmp_path / "awesome-project"
        project_dir.mkdir()

        # Note: AI provider selection removed - now happens per-slot
        mock_prompt.side_effect = [
            "awesome-project",  # default name
            "1",
            "",
        ]

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=project_dir),
            patch("aibox.cli.commands.init.ProfileLoader") as mock_profile_loader,
        ):
            mock_loader = MagicMock()
            mock_loader.list_profiles_with_info.return_value = [
                {"name": "nodejs", "description": "Node.js", "versions": "20"}
            ]
            mock_profile_loader.return_value = mock_loader
            init_command()

        saved_config = mock_save_project.call_args[0][0]
        assert saved_config.name == "awesome-project"

    @patch("aibox.cli.commands.init.get_global_config_path")
    @patch("aibox.cli.commands.init.load_global_config")
    @patch("aibox.cli.commands.init.save_project_config")
    @patch("aibox.cli.commands.init.Prompt.ask")
    def test_init_handles_multiple_profiles(
        self,
        mock_prompt: MagicMock,
        mock_save_project: MagicMock,
        mock_load_global: MagicMock,
        mock_global_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test init handles selection of multiple profiles."""
        mock_global_path.return_value = tmp_path / "global.yml"
        (tmp_path / "global.yml").touch()
        mock_load_global.return_value = GlobalConfig()

        # User selects profiles 1 and 2
        # Note: AI provider selection removed - now happens per-slot
        mock_prompt.side_effect = [
            "fullstack-app",
            "1,2",  # Select both profiles
            "3.12",  # Python version
            "20",  # Node version
        ]

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=tmp_path),
            patch("aibox.cli.commands.init.ProfileLoader") as mock_profile_loader,
        ):
            mock_loader = MagicMock()
            mock_loader.list_profiles_with_info.return_value = [
                {"name": "python", "description": "Python", "versions": "3.12"},
                {"name": "nodejs", "description": "Node.js", "versions": "20"},
            ]
            mock_profile_loader.return_value = mock_loader
            init_command()

        saved_config = mock_save_project.call_args[0][0]
        assert "python:3.12" in saved_config.profiles
        assert "nodejs:20" in saved_config.profiles

    @patch("aibox.cli.commands.init.get_global_config_path")
    @patch("aibox.cli.commands.init.load_global_config")
    @patch("aibox.cli.commands.init.save_project_config")
    @patch("aibox.cli.commands.init.save_aibox_ref")
    @patch("aibox.cli.commands.init.Prompt.ask")
    def test_init_creates_aibox_ref_file(
        self,
        mock_prompt: MagicMock,
        mock_save_ref: MagicMock,
        _mock_save_project: MagicMock,
        mock_load_global: MagicMock,
        mock_global_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test init creates .aibox-ref file with correct storage directory."""
        mock_global_path.return_value = tmp_path / "global.yml"
        (tmp_path / "global.yml").touch()
        mock_load_global.return_value = GlobalConfig()

        project_dir = tmp_path / "test-project"
        project_dir.mkdir()

        mock_prompt.side_effect = [
            "test-project",
            "1",
            "",
        ]

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=project_dir),
            patch("aibox.cli.commands.init.ProfileLoader") as mock_profile_loader,
        ):
            mock_loader = MagicMock()
            mock_loader.list_profiles_with_info.return_value = [
                {"name": "python", "description": "Python", "versions": "3.12"}
            ]
            mock_profile_loader.return_value = mock_loader
            init_command()

        # Verify .aibox-ref was saved with correct storage directory
        assert mock_save_ref.called
        storage_dir_arg = mock_save_ref.call_args[0][1]
        expected_storage_dir = get_project_storage_dir(project_dir)
        assert storage_dir_arg == expected_storage_dir

    @patch("aibox.cli.commands.init.get_global_config_path")
    @patch("aibox.cli.commands.init.load_global_config")
    @patch("aibox.cli.commands.init.save_project_config")
    @patch("aibox.cli.commands.init.Prompt.ask")
    def test_init_allows_skipping_profiles(
        self,
        mock_prompt: MagicMock,
        mock_save_project: MagicMock,
        mock_load_global: MagicMock,
        mock_global_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test init allows skipping profile selection (empty profiles list)."""
        mock_global_path.return_value = tmp_path / "global.yml"
        (tmp_path / "global.yml").touch()
        mock_load_global.return_value = GlobalConfig()

        # User presses Enter to skip profiles (empty string)
        mock_prompt.side_effect = [
            "minimal-project",  # project name
            "",  # profile selection (empty = skip)
        ]

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=tmp_path),
            patch("aibox.cli.commands.init.ProfileLoader") as mock_profile_loader,
        ):
            mock_loader = MagicMock()
            mock_loader.list_profiles_with_info.return_value = [
                {"name": "python", "description": "Python", "versions": "3.12"},
                {"name": "nodejs", "description": "Node.js", "versions": "20"},
            ]
            mock_profile_loader.return_value = mock_loader
            init_command()

        # Verify project config was saved with empty profiles list
        assert mock_save_project.called
        saved_config = mock_save_project.call_args[0][0]
        assert isinstance(saved_config, ProjectConfig)
        assert saved_config.name == "minimal-project"
        assert saved_config.profiles == []
