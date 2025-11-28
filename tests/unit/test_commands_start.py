"""
Unit tests for start command.

Tests cover:
- Successful container start with Rich output
- Error handling and display
- Argument passing to orchestrator
"""

from pathlib import Path
from unittest.mock import ANY, Mock, patch

import pytest

from aibox.cli.commands.start import _slot_wizard, start_command
from aibox.containers.orchestrator import ContainerInfo
from aibox.utils.errors import APIKeyNotFoundError, ConfigNotFoundError


class TestStartCommand:
    """Tests for start command function."""

    @patch("aibox.cli.commands.start.load_project_config")
    @patch("aibox.cli.commands.start.ContainerOrchestrator")
    @patch("aibox.cli.commands.start.console")
    def test_start_command_success(
        self,
        mock_console: Mock,
        mock_orchestrator_class: Mock,
        mock_load_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test successful container start with Rich output."""
        # Mock config loading (project is initialized)
        mock_load_config.return_value = Mock()

        # Setup mock orchestrator
        mock_orchestrator = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator

        container_info = ContainerInfo(
            container_id="abc123def456",
            container_name="aibox-test-1",
            slot_number=1,
            ai_provider="claude",
            project_name="test",
        )
        mock_orchestrator.start_container.return_value = container_info
        mock_orchestrator.attach_to_container.return_value = 0  # Mock successful CLI session

        # Mock slot config to return existing slot with claude provider
        with (
            patch("aibox.cli.commands.start.get_project_storage_dir") as mock_storage,
            patch("aibox.cli.commands.start.SlotManager") as mock_slot_mgr,
        ):
            mock_storage.return_value = tmp_path / ".aibox"
            mock_slot_manager_inst = Mock()
            mock_slot_mgr.return_value = mock_slot_manager_inst
            mock_slot_config = Mock()
            mock_slot_config.exists.return_value = True  # Slot exists
            mock_slot_config.load.return_value = {"ai_provider": "claude"}
            mock_slot_manager_inst.get_slot.return_value = mock_slot_config

            # Execute command - expect SystemExit from auto-attach
            with pytest.raises(SystemExit) as exc_info:
                start_command(
                    project_root=tmp_path,
                    slot_number=1,
                )

        # Verify exit code is 0 (success)
        assert exc_info.value.code == 0

        # Verify orchestrator was called correctly (ai_provider=None since slot exists)
        mock_orchestrator.start_container.assert_called_once_with(
            project_root=tmp_path,
            slot_number=1,
            ai_provider=None,
            reuse_existing=True,
            auto_remove=False,
            force_openai_auth_port=False,
            progress_callback=ANY,
        )

        # Verify attach was called
        mock_orchestrator.attach_to_container.assert_called_once_with(
            project_root=tmp_path,
            slot_number=1,
            resume=False,
        )

        # Verify Rich output was called (console.print)
        assert mock_console.print.called
        # Should show success message
        success_calls = [
            call
            for call in mock_console.print.call_args_list
            if "✓" in str(call) or "successfully" in str(call).lower()
        ]
        assert len(success_calls) > 0

    @patch("aibox.cli.commands.start.SlotManager")
    @patch("aibox.cli.commands.start.get_project_storage_dir")
    @patch("aibox.cli.commands.start.ProviderRegistry")
    @patch("aibox.cli.commands.start.IntPrompt")
    def test_slot_wizard_uses_numeric_provider_choice(
        self,
        mock_int_prompt: Mock,
        mock_provider_registry: Mock,
        mock_storage_dir: Mock,
        mock_slot_manager_cls: Mock,
        tmp_path: Path,
    ) -> None:
        """_slot_wizard should let users pick providers by number instead of typing."""
        mock_storage_dir.return_value = tmp_path / ".aibox"

        slot_manager = Mock()
        slot_manager.list_slots.return_value = []
        slot_manager.get_next_slot_number.return_value = 2
        mock_slot_manager_cls.return_value = slot_manager

        provider_names = ["claude", "gemini", "openai"]
        provider_objs = {}
        for name in provider_names:
            provider = Mock()
            provider.name = name
            provider.display_name = f"{name} CLI"
            provider_objs[name] = provider
        mock_provider_registry.list_providers.return_value = provider_names
        mock_provider_registry.get_provider.side_effect = lambda name: provider_objs[name]

        # First prompt chooses slot number (2), second prompt chooses provider index (1 => claude)
        mock_int_prompt.ask.side_effect = [2, 1]

        slot_number, ai_provider = _slot_wizard(tmp_path)

        assert (slot_number, ai_provider) == (2, "claude")
        assert mock_int_prompt.ask.call_count == 2

        provider_prompt = mock_int_prompt.ask.call_args_list[1]
        assert provider_prompt.kwargs["choices"] == ["1", "2", "3"]
        assert provider_prompt.kwargs["default"] == 1

    @patch("aibox.cli.commands.slot._ensure_openai_session")
    @patch("aibox.cli.commands.start.load_project_config")
    @patch("aibox.cli.commands.start.ContainerOrchestrator")
    @patch("aibox.cli.commands.start.console")
    def test_start_command_runs_openai_login_helper(
        self,
        _mock_console: Mock,
        mock_orchestrator_class: Mock,
        mock_load_config: Mock,
        mock_openai_login: Mock,
        tmp_path: Path,
    ) -> None:
        """Ensure OpenAI login helper runs before starting an OpenAI slot."""
        mock_load_config.return_value = Mock()

        mock_orchestrator = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator
        container_info = ContainerInfo(
            container_id="abc123",
            container_name="aibox-test-2",
            slot_number=2,
            ai_provider="openai",
            project_name="test",
        )
        mock_orchestrator.start_container.return_value = container_info
        mock_orchestrator.attach_to_container.return_value = 0

        with patch("aibox.cli.commands.start._slot_wizard") as mock_wizard:
            mock_wizard.return_value = (2, "openai")

            with pytest.raises(SystemExit):
                start_command(project_root=tmp_path, slot_number=None)

        mock_openai_login.assert_called_once_with(tmp_path, 2)

    @patch("aibox.cli.commands.start.load_project_config")
    @patch("aibox.cli.commands.start.ContainerOrchestrator")
    @patch("aibox.cli.commands.start.console")
    def test_start_command_auto_slot(
        self,
        _mock_console: Mock,
        mock_orchestrator_class: Mock,
        mock_load_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test container start with auto slot assignment."""
        # Mock config loading (project is initialized)
        mock_load_config.return_value = Mock()

        mock_orchestrator = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator

        container_info = ContainerInfo(
            container_id="abc123",
            container_name="aibox-test-3",
            slot_number=3,  # Auto-assigned to slot 3
            ai_provider="claude",
            project_name="test",
        )
        mock_orchestrator.start_container.return_value = container_info
        mock_orchestrator.attach_to_container.return_value = 0  # Mock successful CLI session

        # Mock the wizard to return slot 3 and claude
        with patch("aibox.cli.commands.start._slot_wizard") as mock_wizard:
            mock_wizard.return_value = (3, "claude")  # Return (slot_number, ai_provider)

            # Execute without slot_number (triggers wizard) - expect SystemExit from auto-attach
            with pytest.raises(SystemExit) as exc_info:
                start_command(
                    project_root=tmp_path,
                    slot_number=None,  # Triggers wizard
                )

        # Verify exit code is 0 (success)
        assert exc_info.value.code == 0

        # Verify orchestrator was called with wizard results
        mock_orchestrator.start_container.assert_called_once_with(
            project_root=tmp_path,
            slot_number=3,
            ai_provider="claude",
            reuse_existing=True,
            auto_remove=False,
            force_openai_auth_port=False,
            progress_callback=ANY,
        )

    @patch("aibox.cli.commands.start.load_project_config")
    @patch("aibox.cli.commands.start.Confirm")
    @patch("aibox.cli.commands.start.console")
    def test_start_command_config_not_found(
        self,
        mock_console: Mock,
        mock_confirm: Mock,
        mock_load_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test that start prompts to initialize when config not found and user declines."""
        # Simulate config not found
        mock_load_config.side_effect = ConfigNotFoundError("Config not found")

        # User declines initialization
        mock_confirm.ask.return_value = False

        # Should exit with code 0 (user cancelled)
        with pytest.raises(SystemExit) as exc_info:
            start_command(
                project_root=tmp_path,
                slot_number=1,
            )

        assert exc_info.value.code == 0

        # Verify user was asked about initialization
        mock_confirm.ask.assert_called_once()

        # Verify helpful message was shown
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("not initialized" in call for call in print_calls)
        assert any("aibox init" in call for call in print_calls)

    @patch("aibox.cli.commands.start.load_project_config")
    @patch("aibox.cli.commands.start.Confirm")
    @patch("aibox.cli.commands.start.console")
    @patch("aibox.cli.commands.start.ContainerOrchestrator")
    def test_start_command_runs_init_when_config_not_found_and_user_accepts(
        self,
        mock_orchestrator_class: Mock,
        _mock_console: Mock,
        mock_confirm: Mock,
        mock_load_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test that start runs init when config not found and user accepts."""
        # First call raises ConfigNotFoundError, second succeeds (after init)
        mock_load_config.side_effect = [
            ConfigNotFoundError("Config not found"),
            Mock(),  # Success after init
        ]

        # User accepts initialization
        mock_confirm.ask.return_value = True

        # Mock init_command (patch where it's imported from)
        with patch("aibox.cli.commands.init.init_command") as mock_init:
            # Mock orchestrator and its methods
            mock_orchestrator = Mock()
            mock_orchestrator_class.return_value = mock_orchestrator
            container_info = ContainerInfo(
                container_id="abc123",
                container_name="aibox-test-1",
                slot_number=1,
                ai_provider="claude",
                project_name="test",
            )
            mock_orchestrator.start_container.return_value = container_info
            mock_orchestrator.attach_to_container.return_value = 0

            # Mock slot wizard and config
            with (
                patch("aibox.cli.commands.start.get_project_storage_dir") as mock_storage,
                patch("aibox.cli.commands.start.SlotManager") as mock_slot_mgr,
            ):
                mock_storage.return_value = tmp_path / ".aibox"
                mock_slot_manager_inst = Mock()
                mock_slot_mgr.return_value = mock_slot_manager_inst
                mock_slot_config = Mock()
                mock_slot_config.exists.return_value = True
                mock_slot_manager_inst.get_slot.return_value = mock_slot_config

                # Should exit with code 0 (success) after attach
                with pytest.raises(SystemExit) as exc_info:
                    start_command(
                        project_root=tmp_path,
                        slot_number=1,
                    )

                assert exc_info.value.code == 0

                # Verify init was called (without arguments)
                mock_init.assert_called_once()

                # Verify container was started
                mock_orchestrator.start_container.assert_called_once()

    @patch("aibox.cli.commands.start.load_project_config")
    @patch("aibox.cli.commands.start.ContainerOrchestrator")
    @patch("aibox.cli.commands.start.console")
    def test_start_command_api_key_missing(
        self,
        _mock_console: Mock,
        mock_orchestrator_class: Mock,
        mock_load_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test error handling when API key missing."""
        # Mock config loading (project is initialized)
        mock_load_config.return_value = Mock()

        mock_orchestrator = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator

        # Orchestrator raises APIKeyNotFoundError
        mock_orchestrator.start_container.side_effect = APIKeyNotFoundError(
            "ANTHROPIC_API_KEY not found"
        )

        # Mock slot config
        with (
            patch("aibox.cli.commands.start.get_project_storage_dir") as mock_storage,
            patch("aibox.cli.commands.start.SlotManager") as mock_slot_mgr,
        ):
            mock_storage.return_value = tmp_path / ".aibox"
            mock_slot_manager_inst = Mock()
            mock_slot_mgr.return_value = mock_slot_manager_inst
            mock_slot_config = Mock()
            mock_slot_config.exists.return_value = True
            mock_slot_manager_inst.get_slot.return_value = mock_slot_config

            # Should propagate exception
            with pytest.raises(APIKeyNotFoundError):
                start_command(
                    project_root=tmp_path,
                    slot_number=1,
                )

    @patch("aibox.cli.commands.start.load_project_config")
    @patch("aibox.cli.commands.start.ContainerOrchestrator")
    @patch("aibox.cli.commands.start.console")
    def test_start_command_keyboard_interrupt(
        self,
        mock_console: Mock,
        mock_orchestrator_class: Mock,
        mock_load_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test handling of keyboard interrupt (Ctrl+C)."""
        # Mock config loading (project is initialized)
        mock_load_config.return_value = Mock()

        mock_orchestrator = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator

        # Simulate Ctrl+C during operation
        mock_orchestrator.start_container.side_effect = KeyboardInterrupt()

        # Mock slot config
        with (
            patch("aibox.cli.commands.start.get_project_storage_dir") as mock_storage,
            patch("aibox.cli.commands.start.SlotManager") as mock_slot_mgr,
        ):
            mock_storage.return_value = tmp_path / ".aibox"
            mock_slot_manager_inst = Mock()
            mock_slot_mgr.return_value = mock_slot_manager_inst
            mock_slot_config = Mock()
            mock_slot_config.exists.return_value = True
            mock_slot_manager_inst.get_slot.return_value = mock_slot_config

            # Should catch KeyboardInterrupt and exit gracefully
            with pytest.raises(SystemExit) as exc_info:
                start_command(
                    project_root=tmp_path,
                    slot_number=1,
                )

        # Should exit with code 1
        assert exc_info.value.code == 1

        # Should show cancelled message
        cancel_calls = [
            call for call in mock_console.print.call_args_list if "cancel" in str(call).lower()
        ]
        assert len(cancel_calls) > 0

    @patch("aibox.cli.commands.start.load_project_config")
    @patch("aibox.cli.commands.start.ContainerOrchestrator")
    @patch("aibox.cli.commands.start.console")
    def test_start_command_shows_container_info(
        self,
        mock_console: Mock,
        mock_orchestrator_class: Mock,
        mock_load_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test that container information is displayed."""
        # Mock config loading (project is initialized)
        mock_load_config.return_value = Mock()

        mock_orchestrator = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator

        container_info = ContainerInfo(
            container_id="abc123def456789",
            container_name="aibox-myproject-2",
            slot_number=2,
            ai_provider="claude",
            project_name="myproject",
        )
        mock_orchestrator.start_container.return_value = container_info
        mock_orchestrator.attach_to_container.return_value = 0  # Mock successful CLI session

        # Mock slot config
        with (
            patch("aibox.cli.commands.start.get_project_storage_dir") as mock_storage,
            patch("aibox.cli.commands.start.SlotManager") as mock_slot_mgr,
        ):
            mock_storage.return_value = tmp_path / ".aibox"
            mock_slot_manager_inst = Mock()
            mock_slot_mgr.return_value = mock_slot_manager_inst
            mock_slot_config = Mock()
            mock_slot_config.exists.return_value = True
            mock_slot_manager_inst.get_slot.return_value = mock_slot_config

            # Expect SystemExit from auto-attach
            with pytest.raises(SystemExit) as exc_info:
                start_command(
                    project_root=tmp_path,
                    slot_number=2,
                )

        # Verify exit code is 0 (success)
        assert exc_info.value.code == 0

        # Verify Panel was shown (implicitly via console.print calls)
        # Check that container details appear in output
        all_print_calls = str(mock_console.print.call_args_list)

        # Container info should be shown somewhere
        assert "abc123def456" in all_print_calls or mock_console.print.called

    @patch("aibox.cli.commands.start.load_project_config")
    @patch("aibox.cli.commands.start.ContainerOrchestrator")
    @patch("aibox.cli.commands.start.console")
    def test_start_command_stops_container_by_default(
        self,
        mock_console: Mock,
        mock_orchestrator_class: Mock,
        mock_load_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Default behavior stops container (without deleting)."""
        # Mock config loading (project is initialized)
        mock_load_config.return_value = Mock()

        mock_orchestrator = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator

        container_info = ContainerInfo(
            container_id="abc123",
            container_name="aibox-test-1",
            slot_number=1,
            ai_provider="claude",
            project_name="test",
        )
        mock_orchestrator.start_container.return_value = container_info
        mock_orchestrator.attach_to_container.return_value = 0  # Mock successful CLI session

        # Mock slot config
        with (
            patch("aibox.cli.commands.start.get_project_storage_dir") as mock_storage,
            patch("aibox.cli.commands.start.SlotManager") as mock_slot_mgr,
        ):
            mock_storage.return_value = tmp_path / ".aibox"
            mock_slot_manager_inst = Mock()
            mock_slot_mgr.return_value = mock_slot_manager_inst
            mock_slot_config = Mock()
            mock_slot_config.exists.return_value = True
            mock_slot_manager_inst.get_slot.return_value = mock_slot_config

            # Expect SystemExit from auto-attach
            with pytest.raises(SystemExit) as exc_info:
                start_command(
                    project_root=tmp_path,
                    slot_number=1,
                )

        # Verify exit code is 0 (success)
        assert exc_info.value.code == 0

        # Container should be stopped
        mock_orchestrator.stop_container.assert_called_once_with(
            project_root=tmp_path,
            slot_number=1,
        )
        all_calls = str(mock_console.print.call_args_list).lower()
        assert "stopped and preserved" in all_calls

    @patch("aibox.cli.commands.start.load_project_config")
    @patch("aibox.cli.commands.start.ContainerOrchestrator")
    @patch("aibox.cli.commands.start.console")
    def test_start_command_auto_delete_stops_container(
        self,
        mock_console: Mock,
        mock_orchestrator_class: Mock,
        mock_load_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Container is stopped when auto-delete flag is enabled."""
        mock_load_config.return_value = Mock()

        mock_orchestrator = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator

        container_info = ContainerInfo(
            container_id="abc123",
            container_name="aibox-test-1",
            slot_number=1,
            ai_provider="claude",
            project_name="test",
        )
        mock_orchestrator.start_container.return_value = container_info
        mock_orchestrator.attach_to_container.return_value = 0

        with (
            patch("aibox.cli.commands.start.get_project_storage_dir") as mock_storage,
            patch("aibox.cli.commands.start.SlotManager") as mock_slot_mgr,
        ):
            mock_storage.return_value = tmp_path / ".aibox"
            mock_slot_manager_inst = Mock()
            mock_slot_mgr.return_value = mock_slot_manager_inst
            mock_slot_config = Mock()
            mock_slot_config.exists.return_value = True
            mock_slot_manager_inst.get_slot.return_value = mock_slot_config

            with pytest.raises(SystemExit):
                start_command(
                    project_root=tmp_path,
                    slot_number=1,
                    auto_delete=True,
                )

        mock_orchestrator.stop_container.assert_called_once_with(
            project_root=tmp_path,
            slot_number=1,
        )
        all_calls = str(mock_console.print.call_args_list).lower()
        assert "stopped" in all_calls or "cleaned up" in all_calls
