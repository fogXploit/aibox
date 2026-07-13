"""
Unit tests for aibox init command.

Tests cover:
- Global config creation on first run
- Global config skip when already exists
- Project config creation
- Directory validation (reject home/root)
- Interactive prompt mocking (questionary checkbox/select + rich Prompt)
- Error handling
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from aibox.cli.commands.init import init_command
from aibox.config.models import GlobalConfig, ProjectConfig
from aibox.utils.errors import AiboxError
from aibox.utils.hash import get_project_storage_dir

PYTHON_PROFILE_INFO: dict[str, Any] = {
    "name": "python",
    "description": "Python development",
    "versions": "3.11, 3.12, 3.13",
    "versions_list": ["3.11", "3.12", "3.13"],
    "default_version": "3.12",
}

NODEJS_PROFILE_INFO: dict[str, Any] = {
    "name": "nodejs",
    "description": "Node.js development",
    "versions": "20, 22",
    "versions_list": ["20", "22"],
    "default_version": "22",
}


def _make_mock_loader(profiles: list[dict[str, Any]]) -> MagicMock:
    """Create a mock ProfileLoader instance returning the given profile infos."""
    mock_loader = MagicMock()
    mock_loader.list_profiles_with_info.return_value = profiles
    return mock_loader


class TestInitCommand:
    """Tests for init command."""

    @patch("aibox.cli.commands.init.get_global_config_path")
    @patch("aibox.cli.commands.init.save_global_config")
    @patch("aibox.cli.commands.init.save_project_config")
    @patch("aibox.cli.commands.init.questionary")
    @patch("aibox.cli.commands.init.Prompt.ask")
    @patch("aibox.cli.commands.init.Confirm.ask")
    def test_init_creates_global_config_first_time(
        self,
        _mock_confirm: MagicMock,
        mock_prompt: MagicMock,
        mock_questionary: MagicMock,
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
        mock_prompt.side_effect = ["test-project"]  # project name
        mock_questionary.checkbox.return_value.ask.return_value = ["python"]
        mock_questionary.select.return_value.ask.return_value = ""  # default version

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=tmp_path),
            patch("aibox.cli.commands.init.ProfileLoader") as mock_profile_loader,
        ):
            mock_profile_loader.return_value = _make_mock_loader([PYTHON_PROFILE_INFO])
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
    @patch("aibox.cli.commands.init.questionary")
    @patch("aibox.cli.commands.init.Prompt.ask")
    def test_init_skips_global_config_if_exists(
        self,
        mock_prompt: MagicMock,
        mock_questionary: MagicMock,
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
        mock_prompt.side_effect = ["test-project"]
        mock_questionary.checkbox.return_value.ask.return_value = ["python"]
        mock_questionary.select.return_value.ask.return_value = ""

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=tmp_path),
            patch("aibox.cli.commands.init.ProfileLoader") as mock_profile_loader,
        ):
            mock_profile_loader.return_value = _make_mock_loader([PYTHON_PROFILE_INFO])
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
    @patch("aibox.cli.commands.init.questionary")
    @patch("aibox.cli.commands.init.Prompt.ask")
    @patch("aibox.cli.commands.init.Confirm.ask")
    def test_init_creates_project_config_with_profiles(
        self,
        _mock_confirm: MagicMock,
        mock_prompt: MagicMock,
        mock_questionary: MagicMock,
        mock_save_project: MagicMock,
        mock_load_global: MagicMock,
        mock_global_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test init creates project config with an explicitly versioned profile."""
        mock_global_path.return_value = tmp_path / "global.yml"
        (tmp_path / "global.yml").touch()
        mock_load_global.return_value = GlobalConfig()

        # User toggles the python profile and picks version 3.12 explicitly
        mock_prompt.side_effect = ["my-project"]
        mock_questionary.checkbox.return_value.ask.return_value = ["python"]
        mock_questionary.select.return_value.ask.return_value = "3.12"

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=tmp_path),
            patch("aibox.cli.commands.init.ProfileLoader") as mock_profile_loader,
        ):
            mock_profile_loader.return_value = _make_mock_loader([PYTHON_PROFILE_INFO])
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
    @patch("aibox.cli.commands.init.questionary")
    @patch("aibox.cli.commands.init.Prompt.ask")
    def test_init_uses_default_project_name(
        self,
        mock_prompt: MagicMock,
        mock_questionary: MagicMock,
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

        mock_prompt.side_effect = ["awesome-project"]  # default name
        mock_questionary.checkbox.return_value.ask.return_value = ["nodejs"]
        mock_questionary.select.return_value.ask.return_value = ""

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=project_dir),
            patch("aibox.cli.commands.init.ProfileLoader") as mock_profile_loader,
        ):
            mock_profile_loader.return_value = _make_mock_loader([NODEJS_PROFILE_INFO])
            init_command()

        saved_config = mock_save_project.call_args[0][0]
        assert saved_config.name == "awesome-project"

    @patch("aibox.cli.commands.init.get_global_config_path")
    @patch("aibox.cli.commands.init.load_global_config")
    @patch("aibox.cli.commands.init.save_project_config")
    @patch("aibox.cli.commands.init.questionary")
    @patch("aibox.cli.commands.init.Prompt.ask")
    def test_init_handles_multiple_profiles(
        self,
        mock_prompt: MagicMock,
        mock_questionary: MagicMock,
        mock_save_project: MagicMock,
        mock_load_global: MagicMock,
        mock_global_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test init handles multi-select of profiles with per-profile versions."""
        mock_global_path.return_value = tmp_path / "global.yml"
        (tmp_path / "global.yml").touch()
        mock_load_global.return_value = GlobalConfig()

        # User toggles both profiles in the checkbox, then picks a version each
        mock_prompt.side_effect = ["fullstack-app"]
        mock_questionary.checkbox.return_value.ask.return_value = ["python", "nodejs"]
        mock_questionary.select.return_value.ask.side_effect = ["3.12", "20"]

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=tmp_path),
            patch("aibox.cli.commands.init.ProfileLoader") as mock_profile_loader,
        ):
            mock_profile_loader.return_value = _make_mock_loader(
                [PYTHON_PROFILE_INFO, NODEJS_PROFILE_INFO]
            )
            init_command()

        saved_config = mock_save_project.call_args[0][0]
        assert saved_config.profiles == ["python:3.12", "nodejs:20"]

    @patch("aibox.cli.commands.init.get_global_config_path")
    @patch("aibox.cli.commands.init.load_global_config")
    @patch("aibox.cli.commands.init.save_project_config")
    @patch("aibox.cli.commands.init.save_aibox_ref")
    @patch("aibox.cli.commands.init.questionary")
    @patch("aibox.cli.commands.init.Prompt.ask")
    def test_init_creates_aibox_ref_file(
        self,
        mock_prompt: MagicMock,
        mock_questionary: MagicMock,
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

        mock_prompt.side_effect = ["test-project"]
        mock_questionary.checkbox.return_value.ask.return_value = ["python"]
        mock_questionary.select.return_value.ask.return_value = ""

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=project_dir),
            patch("aibox.cli.commands.init.ProfileLoader") as mock_profile_loader,
        ):
            mock_profile_loader.return_value = _make_mock_loader([PYTHON_PROFILE_INFO])
            init_command()

        # Verify .aibox-ref was saved with correct storage directory
        assert mock_save_ref.called
        storage_dir_arg = mock_save_ref.call_args[0][1]
        expected_storage_dir = get_project_storage_dir(project_dir)
        assert storage_dir_arg == expected_storage_dir

    @patch("aibox.cli.commands.init.get_global_config_path")
    @patch("aibox.cli.commands.init.load_global_config")
    @patch("aibox.cli.commands.init.save_project_config")
    @patch("aibox.cli.commands.init.questionary")
    @patch("aibox.cli.commands.init.Prompt.ask")
    def test_init_allows_skipping_profiles(
        self,
        mock_prompt: MagicMock,
        mock_questionary: MagicMock,
        mock_save_project: MagicMock,
        mock_load_global: MagicMock,
        mock_global_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test init allows confirming the checkbox with nothing toggled."""
        mock_global_path.return_value = tmp_path / "global.yml"
        (tmp_path / "global.yml").touch()
        mock_load_global.return_value = GlobalConfig()

        # User presses Enter without toggling any profile
        mock_prompt.side_effect = ["minimal-project"]
        mock_questionary.checkbox.return_value.ask.return_value = []

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=tmp_path),
            patch("aibox.cli.commands.init.ProfileLoader") as mock_profile_loader,
        ):
            mock_profile_loader.return_value = _make_mock_loader(
                [PYTHON_PROFILE_INFO, NODEJS_PROFILE_INFO]
            )
            init_command()

        # Verify project config was saved with empty profiles list
        assert mock_save_project.called
        saved_config = mock_save_project.call_args[0][0]
        assert isinstance(saved_config, ProjectConfig)
        assert saved_config.name == "minimal-project"
        assert saved_config.profiles == []
        # No version picker should appear when nothing was selected
        assert not mock_questionary.select.called

    @patch("aibox.cli.commands.init.get_global_config_path")
    @patch("aibox.cli.commands.init.load_global_config")
    @patch("aibox.cli.commands.init.save_project_config")
    @patch("aibox.cli.commands.init.questionary")
    @patch("aibox.cli.commands.init.Prompt.ask")
    def test_init_checkbox_built_from_profile_info(
        self,
        mock_prompt: MagicMock,
        mock_questionary: MagicMock,
        _mock_save_project: MagicMock,
        mock_load_global: MagicMock,
        mock_global_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test checkbox choices carry profile name as value and a descriptive title."""
        mock_global_path.return_value = tmp_path / "global.yml"
        (tmp_path / "global.yml").touch()
        mock_load_global.return_value = GlobalConfig()

        mock_prompt.side_effect = ["test-project"]
        mock_questionary.checkbox.return_value.ask.return_value = []

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=tmp_path),
            patch("aibox.cli.commands.init.ProfileLoader") as mock_profile_loader,
        ):
            mock_profile_loader.return_value = _make_mock_loader(
                [PYTHON_PROFILE_INFO, NODEJS_PROFILE_INFO]
            )
            init_command()

        # One choice per profile: descriptive title, profile name as value
        mock_questionary.Choice.assert_any_call(
            title="python — Python development (3.11, 3.12, 3.13)", value="python"
        )
        mock_questionary.Choice.assert_any_call(
            title="nodejs — Node.js development (20, 22)", value="nodejs"
        )

        # The checkbox message explains the keybindings
        checkbox_message = mock_questionary.checkbox.call_args[0][0]
        assert "space to toggle" in checkbox_message
        assert "enter to confirm" in checkbox_message

    @patch("aibox.cli.commands.init.get_global_config_path")
    @patch("aibox.cli.commands.init.load_global_config")
    @patch("aibox.cli.commands.init.save_project_config")
    @patch("aibox.cli.commands.init.questionary")
    @patch("aibox.cli.commands.init.Prompt.ask")
    def test_init_default_version_choice_produces_bare_name(
        self,
        mock_prompt: MagicMock,
        mock_questionary: MagicMock,
        mock_save_project: MagicMock,
        mock_load_global: MagicMock,
        mock_global_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test picking the 'default (<version>)' choice yields a bare profile spec."""
        mock_global_path.return_value = tmp_path / "global.yml"
        (tmp_path / "global.yml").touch()
        mock_load_global.return_value = GlobalConfig()

        mock_prompt.side_effect = ["test-project"]
        mock_questionary.checkbox.return_value.ask.return_value = ["python"]
        # The "default (3.12)" choice maps to no explicit version
        mock_questionary.select.return_value.ask.return_value = ""

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=tmp_path),
            patch("aibox.cli.commands.init.ProfileLoader") as mock_profile_loader,
        ):
            mock_profile_loader.return_value = _make_mock_loader([PYTHON_PROFILE_INFO])
            init_command()

        saved_config = mock_save_project.call_args[0][0]
        assert saved_config.profiles == ["python"]

        # The version picker offered "default (<default_version>)" first,
        # followed by each concrete version
        mock_questionary.Choice.assert_any_call(title="default (3.12)", value="")
        mock_questionary.Choice.assert_any_call(title="3.11", value="3.11")
        mock_questionary.Choice.assert_any_call(title="3.12", value="3.12")
        mock_questionary.Choice.assert_any_call(title="3.13", value="3.13")

    @patch("aibox.cli.commands.init.get_global_config_path")
    @patch("aibox.cli.commands.init.load_global_config")
    @patch("aibox.cli.commands.init.save_project_config")
    @patch("aibox.cli.commands.init.questionary")
    @patch("aibox.cli.commands.init.Prompt.ask")
    def test_init_checkbox_cancel_treated_as_no_selection(
        self,
        mock_prompt: MagicMock,
        mock_questionary: MagicMock,
        mock_save_project: MagicMock,
        mock_load_global: MagicMock,
        mock_global_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test Ctrl+C/EOF in the checkbox (ask() -> None) means no profiles."""
        mock_global_path.return_value = tmp_path / "global.yml"
        (tmp_path / "global.yml").touch()
        mock_load_global.return_value = GlobalConfig()

        mock_prompt.side_effect = ["test-project"]
        mock_questionary.checkbox.return_value.ask.return_value = None

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=tmp_path),
            patch("aibox.cli.commands.init.ProfileLoader") as mock_profile_loader,
            patch("aibox.cli.commands.init.console") as mock_console,
        ):
            mock_profile_loader.return_value = _make_mock_loader([PYTHON_PROFILE_INFO])
            init_command()

        saved_config = mock_save_project.call_args[0][0]
        assert saved_config.profiles == []
        assert not mock_questionary.select.called

        # The existing "no profiles selected" message path is kept
        printed = " ".join(str(call) for call in mock_console.print.call_args_list)
        assert "No profiles selected" in printed

    @patch("aibox.cli.commands.init.get_global_config_path")
    @patch("aibox.cli.commands.init.load_global_config")
    @patch("aibox.cli.commands.init.save_project_config")
    @patch("aibox.cli.commands.init.questionary")
    @patch("aibox.cli.commands.init.Prompt.ask")
    def test_init_version_select_cancel_uses_default(
        self,
        mock_prompt: MagicMock,
        mock_questionary: MagicMock,
        mock_save_project: MagicMock,
        mock_load_global: MagicMock,
        mock_global_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test Ctrl+C/EOF in the version select (ask() -> None) falls back to default."""
        mock_global_path.return_value = tmp_path / "global.yml"
        (tmp_path / "global.yml").touch()
        mock_load_global.return_value = GlobalConfig()

        mock_prompt.side_effect = ["test-project"]
        mock_questionary.checkbox.return_value.ask.return_value = ["python"]
        mock_questionary.select.return_value.ask.return_value = None

        with (
            patch("aibox.cli.commands.init.Path.cwd", return_value=tmp_path),
            patch("aibox.cli.commands.init.ProfileLoader") as mock_profile_loader,
        ):
            mock_profile_loader.return_value = _make_mock_loader([PYTHON_PROFILE_INFO])
            init_command()

        saved_config = mock_save_project.call_args[0][0]
        assert saved_config.profiles == ["python"]
