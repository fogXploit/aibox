"""Unit tests for status command."""

from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from aibox.cli.commands.status import status_command


@pytest.fixture
def mock_console() -> MagicMock:
    """Mock Rich console."""
    return MagicMock(spec=Console)


@pytest.fixture
def temp_project_root(tmp_path):
    """Create temporary project root."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    return project_root


class TestStatusCommand:
    """Tests for status_command."""

    @patch("aibox.cli.commands.status.ContainerManager")
    @patch("aibox.cli.commands.status.SlotManager")
    @patch("aibox.cli.commands.status.get_project_storage_dir")
    @patch("aibox.cli.commands.status.load_config")
    @patch("aibox.cli.commands.status.console")
    def test_status_shows_slots_and_config(
        self,
        mock_console,
        mock_load_config,
        mock_storage_dir,
        mock_slot_mgr_class,
        mock_container_mgr_class,
        temp_project_root,
    ) -> None:
        """Status shows project config and slot summaries."""
        mock_load_config.return_value = MagicMock(
            project=MagicMock(
                name="test-project",
                profiles=["python:3.12", "nodejs:20"],
                mounts=[],
                environment={"DEBUG": "1"},
            ),
            global_config=MagicMock(docker=MagicMock(base_image="debian:bookworm-slim")),
        )
        mock_storage_dir.return_value = "test-project-abc12345"
        mock_slot_mgr = MagicMock()
        mock_slot_mgr_class.return_value = mock_slot_mgr
        mock_slot_mgr.list_slots.return_value = [
            {"slot": 1, "container_name": "aibox-project-1", "ai_provider": "claude"},
            {"slot": 2, "container_name": "aibox-project-2", "ai_provider": "openai"},
        ]
        mock_container_mgr = MagicMock()
        mock_container_mgr_class.return_value = mock_container_mgr
        mock_container_mgr.is_container_running.side_effect = [True, False]

        status_command(project_root=temp_project_root)

        mock_load_config.assert_called_once_with(str(temp_project_root))
        mock_slot_mgr.list_slots.assert_called_once()
        # Ensure we checked running status for each container
        assert mock_container_mgr.is_container_running.call_count == 2
        # Verify console received some output
        assert mock_console.print.call_count > 0

    @patch("aibox.cli.commands.status.ContainerManager")
    @patch("aibox.cli.commands.status.SlotManager")
    @patch("aibox.cli.commands.status.get_project_storage_dir")
    @patch("aibox.cli.commands.status.load_config")
    @patch("aibox.cli.commands.status.console")
    def test_status_handles_no_slots(
        self,
        mock_console,
        mock_load_config,
        mock_storage_dir,
        mock_slot_mgr_class,
        mock_container_mgr_class,
        temp_project_root,
    ) -> None:
        """Status shows empty slot message when no slots exist."""
        mock_load_config.return_value = MagicMock(
            project=MagicMock(
                name="test-project",
                profiles=["python:3.12"],
                mounts=[],
                environment={},
            ),
            global_config=MagicMock(docker=MagicMock(base_image="debian:bookworm-slim")),
        )
        mock_storage_dir.return_value = "test-project-abc12345"
        mock_slot_mgr = MagicMock()
        mock_slot_mgr_class.return_value = mock_slot_mgr
        mock_slot_mgr.list_slots.return_value = []
        mock_container_mgr_class.return_value = MagicMock()

        status_command(project_root=temp_project_root)

        mock_slot_mgr.list_slots.assert_called_once()
        # Expect at least one print (config or "no slots")
        assert mock_console.print.call_count > 0
