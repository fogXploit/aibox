"""Unit tests for profile commands."""

from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from aibox.cli.commands.profile import profile_info, profile_list
from aibox.profiles.models import ProfileDefinition


@pytest.fixture
def mock_console():
    """Mock Rich console."""
    return MagicMock(spec=Console)


class TestProfileList:
    """Tests for profile_list command."""

    @patch("aibox.cli.commands.profile.ProfileLoader")
    @patch("aibox.cli.commands.profile.console")
    def test_profile_list_success(self, mock_console, mock_loader_class):
        """Test profile_list displays profiles."""
        # Setup
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.list_profiles.return_value = ["python", "nodejs"]

        python_profile = ProfileDefinition(
            name="python",
            description="Python development",
            versions=["3.11", "3.12"],
            default_version="3.12",
            package_manager="uv",
            system_dependencies=[],
            install_commands=[],
            docker_layers=[],
        )
        nodejs_profile = ProfileDefinition(
            name="nodejs",
            description="Node.js development",
            versions=["18", "20"],
            default_version="20",
            package_manager="npm",
            system_dependencies=[],
            install_commands=[],
            docker_layers=[],
        )

        mock_loader.load_profile.side_effect = [(python_profile, "3.12"), (nodejs_profile, "20")]

        # Execute
        profile_list()

        # Verify
        mock_loader.list_profiles.assert_called_once()
        assert mock_loader.load_profile.call_count == 2
        mock_console.print.assert_called()

    @patch("aibox.cli.commands.profile.ProfileLoader")
    @patch("aibox.cli.commands.profile.console")
    def test_profile_list_empty(self, mock_console, mock_loader_class):
        """Test profile_list with no profiles."""
        # Setup
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.list_profiles.return_value = []

        # Execute
        profile_list()

        # Verify
        mock_loader.list_profiles.assert_called_once()
        mock_console.print.assert_any_call("[yellow]No profiles found[/yellow]")

    @patch("aibox.cli.commands.profile.ProfileLoader")
    @patch("aibox.cli.commands.profile.console")
    def test_profile_list_handles_errors(self, mock_console, mock_loader_class):
        """Test profile_list handles errors gracefully."""
        # Setup
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.list_profiles.side_effect = Exception("Failed to load")

        # Execute and verify
        with pytest.raises(Exception, match="Failed to load"):
            profile_list()

        mock_console.print.assert_called()


class TestProfileInfo:
    """Tests for profile_info command."""

    @patch("aibox.cli.commands.profile.ProfileLoader")
    @patch("aibox.cli.commands.profile.console")
    def test_profile_info_success(self, mock_console, mock_loader_class):
        """Test profile_info displays profile details."""
        # Setup
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader

        profile = ProfileDefinition(
            name="python",
            description="Python development",
            versions=["3.11", "3.12"],
            default_version="3.12",
            package_manager="uv",
            system_dependencies=["python3-dev"],
            install_commands=["pip install uv"],
            docker_layers=["RUN apt-get install python3-dev"],
        )
        mock_loader.load_profile.return_value = (profile, "3.12")

        # Execute
        profile_info("python")

        # Verify
        mock_loader.load_profile.assert_called_once_with("python")
        mock_console.print.assert_called()

    @patch("aibox.cli.commands.profile.ProfileLoader")
    @patch("aibox.cli.commands.profile.console")
    def test_profile_info_with_version(self, _mock_console, mock_loader_class):
        """Test profile_info with version specification."""
        # Setup
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader

        profile = ProfileDefinition(
            name="python",
            description="Python development",
            versions=["3.11", "3.12"],
            default_version="3.12",
            package_manager="uv",
            system_dependencies=[],
            install_commands=[],
            docker_layers=[],
        )
        mock_loader.load_profile.return_value = (profile, "3.12")

        # Execute
        profile_info("python:3.12")

        # Verify - should parse name and ignore version for loading
        mock_loader.load_profile.assert_called_once_with("python")

    @patch("aibox.cli.commands.profile.ProfileLoader")
    @patch("aibox.cli.commands.profile.console")
    def test_profile_info_not_found(self, mock_console, mock_loader_class):
        """Test profile_info with non-existent profile."""
        # Setup
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load_profile.side_effect = FileNotFoundError()

        # Execute and verify
        with pytest.raises(SystemExit):
            profile_info("nonexistent")

        mock_console.print.assert_called()

    @patch("aibox.cli.commands.profile.ProfileLoader")
    @patch("aibox.cli.commands.profile.console")
    def test_profile_info_handles_errors(self, mock_console, mock_loader_class):
        """Test profile_info handles errors gracefully."""
        # Setup
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load_profile.side_effect = Exception("Failed to load")

        # Execute and verify
        with pytest.raises(Exception, match="Failed to load"):
            profile_info("python")

        mock_console.print.assert_called()
