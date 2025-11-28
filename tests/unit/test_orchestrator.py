"""
Unit tests for Container Orchestrator.

The orchestrator coordinates all services to start/stop containers.
Tests cover the full business logic flow with all dependencies mocked.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aibox.config.models import Config, ProjectConfig
from aibox.containers.orchestrator import ContainerInfo, ContainerOrchestrator
from aibox.utils.errors import (
    APIKeyNotFoundError,
    ConfigNotFoundError,
    DockerError,
    ImageBuildError,
    NoAvailableSlotsError,
)


class TestContainerOrchestratorInit:
    """Tests for ContainerOrchestrator initialization."""

    def test_init(self) -> None:
        """Test orchestrator initializes correctly."""
        orchestrator = ContainerOrchestrator()
        assert orchestrator is not None


class TestContainerOrchestratorStartContainer:
    """Tests for start_container method."""

    @patch("aibox.containers.orchestrator.get_project_storage_dir")
    @patch("aibox.containers.orchestrator.ProfileLoader")
    @patch("aibox.containers.orchestrator.load_config")
    @patch("aibox.containers.orchestrator.ProviderRegistry")
    @patch("aibox.containers.orchestrator.SlotManager")
    @patch("aibox.containers.orchestrator.DockerfileGenerator")
    @patch("aibox.containers.orchestrator.ContainerManager")
    @patch("aibox.containers.orchestrator.VolumeManager")
    def test_start_container_success_manual_slot(
        self,
        mock_volume_mgr: Mock,
        mock_container_mgr: Mock,
        mock_dockerfile_gen: Mock,
        mock_slot_mgr: Mock,
        mock_registry: Mock,
        mock_load_config: Mock,
        mock_profile_loader: Mock,
        mock_storage_dir: Mock,
        tmp_path: Path,
    ) -> None:
        """Test successful container start with manual slot."""
        # Setup mocks
        mock_storage_dir.return_value = "test-project-abc123"

        config = Config(
            project=ProjectConfig(
                name="test-project",
                profiles=["python:3.12"],
            )
        )
        mock_load_config.return_value = config

        # Mock ProfileLoader
        mock_loader = Mock()
        mock_profile_loader.return_value = mock_loader
        from aibox.profiles.models import ProfileDefinition

        mock_loader.load_profile.return_value = (
            ProfileDefinition(
                name="python",
                description="Python",
                versions=["3.12"],
                default_version="3.12",
                package_manager="uv",
                system_dependencies=[],
                install_commands=[],
                docker_layers=[],
            ),
            "3.12",
        )

        mock_provider = Mock()
        mock_provider.validate_config = Mock()
        mock_provider.get_docker_env_vars.return_value = {"ANTHROPIC_API_KEY": "test-key"}
        mock_provider.get_required_ports.return_value = {}
        mock_registry.get_provider.return_value = mock_provider

        mock_dockerfile_gen.return_value.generate.return_value = (
            "FROM debian:bookworm-slim\nRUN echo base"
        )
        mock_dockerfile_gen.return_value.generate_provider_layer.return_value = (
            "FROM aibox-test-project-base:hash\nRUN npm install -g provider"
        )
        mock_dockerfile_gen.return_value.generate_build_args.return_value = {
            "PYTHON_VERSION": "3.12"
        }

        mock_container = Mock()
        mock_container.id = "container-123"
        mock_container.name = "aibox-test-project-1"
        # Base check (miss/hit) then provider check (miss/hit)
        mock_container_mgr.return_value.image_exists.side_effect = [False, True, False, True]
        mock_container_mgr.return_value.build_image = Mock()
        mock_container_mgr.return_value.tag_image = Mock()
        mock_container_mgr.return_value.prune_dangling_images.return_value = {
            "ImagesDeleted": [],
            "SpaceReclaimed": 0,
        }
        mock_container_mgr.return_value.create_container.return_value = mock_container
        mock_container_mgr.return_value.start_container = Mock()
        mock_container_mgr.return_value.get_container.return_value = mock_container
        # Mock exec_in_container to simulate CLI already installed
        mock_container_mgr.return_value.exec_in_container.return_value = (0, b"")

        mock_volume_mgr.return_value.prepare_volumes.return_value = {
            "/host/project": {"bind": "/workspace", "mode": "rw"}
        }

        # Mock SlotManager and SlotConfig
        mock_slot_config = Mock()
        mock_slot_config.save = Mock()
        mock_slot_config.get_ai_provider.return_value = None  # No pre-configured provider
        mock_slot_mgr.return_value.get_slot.return_value = mock_slot_config
        mock_container_mgr.return_value.get_container.return_value = None

        # Execute
        orchestrator = ContainerOrchestrator()
        result = orchestrator.start_container(
            project_root=tmp_path,
            slot_number=1,
            ai_provider="claude",
        )

        # Verify
        assert isinstance(result, ContainerInfo)
        assert result.container_id == "container-123"
        assert result.container_name == "aibox-test-project-1"
        assert result.slot_number == 1
        mock_provider.get_required_ports.assert_called_once_with(
            force_auth_port=False,
            project_storage_dir="test-project-abc123",
            slot_number=1,
        )

        # Note: generate_project_hash is no longer called directly in orchestrator
        # It's only called internally by get_project_storage_dir
        mock_load_config.assert_called_once_with(str(tmp_path))
        mock_provider.validate_config.assert_called_once()
        mock_loader.load_profile.assert_called_once_with("python:3.12")
        mock_dockerfile_gen.return_value.generate.assert_called_once()
        mock_dockerfile_gen.return_value.generate_provider_layer.assert_called_once()
        assert mock_container_mgr.return_value.build_image.call_count == 2
        mock_container_mgr.return_value.create_container.assert_called_once()
        mock_container_mgr.return_value.start_container.assert_called_once_with(mock_container)
        mock_slot_config.save.assert_called_once()

    @patch("aibox.containers.orchestrator.load_config")
    @patch("aibox.containers.orchestrator.ProviderRegistry")
    @patch("aibox.containers.orchestrator.SlotManager")
    @patch("aibox.containers.orchestrator.DockerfileGenerator")
    @patch("aibox.containers.orchestrator.ContainerManager")
    @patch("aibox.containers.orchestrator.VolumeManager")
    def test_start_container_auto_slot_assignment(
        self,
        mock_volume_mgr: Mock,
        mock_container_mgr: Mock,
        mock_dockerfile_gen: Mock,
        mock_slot_mgr: Mock,
        mock_registry: Mock,
        mock_load_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test container start with automatic slot assignment."""
        config = Config(project=ProjectConfig(name="test"))
        mock_load_config.return_value = config

        mock_provider = Mock()
        mock_provider.validate_config = Mock()
        mock_provider.get_docker_env_vars.return_value = {}
        mock_provider.get_required_ports.return_value = {}
        mock_registry.get_provider.return_value = mock_provider

        # Auto-assign slot 3
        mock_slot_mgr.return_value.find_available_slot.return_value = 3

        mock_dockerfile_gen.return_value.generate.return_value = "FROM debian:bookworm-slim"
        mock_dockerfile_gen.return_value.generate_provider_layer.return_value = (
            "FROM base\nRUN npm install -g provider"
        )
        mock_dockerfile_gen.return_value.generate_build_args.return_value = {}

        mock_container = Mock()
        mock_container.id = "container-123"
        mock_container_mgr.return_value.image_exists.side_effect = [False, True, False, True]
        mock_container_mgr.return_value.build_image = Mock()
        mock_container_mgr.return_value.create_container.return_value = mock_container
        mock_container_mgr.return_value.start_container = Mock()
        mock_container_mgr.return_value.get_container.return_value = None
        mock_container_mgr.return_value.exec_in_container.return_value = (0, b"")

        mock_volume_mgr.return_value.prepare_volumes.return_value = {}
        mock_slot_mgr.return_value.save_slot_info = Mock()

        orchestrator = ContainerOrchestrator()
        result = orchestrator.start_container(
            project_root=tmp_path,
            slot_number=None,  # Auto-assign
            ai_provider="claude",
        )

        assert result.slot_number == 3
        mock_slot_mgr.return_value.find_available_slot.assert_called_once()

    @patch("aibox.containers.orchestrator.load_config")
    def test_start_container_config_not_found(
        self,
        mock_load_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test error when configuration not found."""
        mock_load_config.side_effect = ConfigNotFoundError("Config not found")

        orchestrator = ContainerOrchestrator()

        with pytest.raises(ConfigNotFoundError):
            orchestrator.start_container(
                project_root=tmp_path,
                slot_number=1,
                ai_provider="claude",
            )

    @patch("aibox.containers.orchestrator.load_config")
    @patch("aibox.containers.orchestrator.ProviderRegistry")
    def test_start_container_api_key_missing(
        self,
        mock_registry: Mock,
        mock_load_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test error when API key validation fails."""
        config = Config(project=ProjectConfig(name="test"))
        mock_load_config.return_value = config

        mock_provider = Mock()
        mock_provider.validate_config.side_effect = APIKeyNotFoundError("API key missing")
        mock_registry.get_provider.return_value = mock_provider

        orchestrator = ContainerOrchestrator()

        with pytest.raises(APIKeyNotFoundError):
            orchestrator.start_container(
                project_root=tmp_path,
                slot_number=1,
                ai_provider="claude",
            )

    @patch("aibox.containers.orchestrator.load_config")
    @patch("aibox.containers.orchestrator.ProviderRegistry")
    @patch("aibox.containers.orchestrator.SlotManager")
    def test_start_container_no_available_slots(
        self,
        mock_slot_mgr: Mock,
        mock_registry: Mock,
        mock_load_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test error when all slots are in use."""
        config = Config(project=ProjectConfig(name="test"))
        mock_load_config.return_value = config

        mock_provider = Mock()
        mock_provider.validate_config = Mock()
        mock_registry.get_provider.return_value = mock_provider

        mock_slot_mgr.return_value.find_available_slot.side_effect = NoAvailableSlotsError(
            "All slots in use"
        )

        orchestrator = ContainerOrchestrator()

        with pytest.raises(NoAvailableSlotsError):
            orchestrator.start_container(
                project_root=tmp_path,
                slot_number=None,  # Triggers auto-assignment
                ai_provider="claude",
            )

    @patch("aibox.containers.orchestrator.load_config")
    @patch("aibox.containers.orchestrator.ProviderRegistry")
    @patch("aibox.containers.orchestrator.SlotManager")
    @patch("aibox.containers.orchestrator.DockerfileGenerator")
    @patch("aibox.containers.orchestrator.ContainerManager")
    def test_start_container_image_build_fails(
        self,
        mock_container_mgr: Mock,
        mock_dockerfile_gen: Mock,
        mock_slot_mgr: Mock,
        mock_registry: Mock,
        mock_load_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test error handling when Docker image build fails."""
        config = Config(project=ProjectConfig(name="test", profiles=["python:3.12"]))
        mock_load_config.return_value = config

        mock_provider = Mock()
        mock_provider.validate_config = Mock()
        mock_registry.get_provider.return_value = mock_provider

        mock_dockerfile_gen.return_value.generate.return_value = "FROM debian:bookworm-slim"

        # Mock image_exists to return False to trigger build
        mock_container_mgr.return_value.image_exists.return_value = False
        mock_container_mgr.return_value.build_image.side_effect = ImageBuildError("Build failed")

        # Mock SlotManager
        mock_slot_config = Mock()
        mock_slot_config.get_ai_provider.return_value = None
        mock_slot_mgr.return_value.get_slot.return_value = mock_slot_config

        orchestrator = ContainerOrchestrator()

        with (
            patch("aibox.containers.orchestrator.VolumeManager"),
            patch("aibox.containers.orchestrator.ProfileLoader"),
            patch("aibox.containers.orchestrator.get_project_storage_dir"),
            pytest.raises(ImageBuildError),
        ):
            orchestrator.start_container(
                project_root=tmp_path,
                slot_number=1,
                ai_provider="claude",
            )

    @patch("aibox.containers.orchestrator.load_config")
    @patch("aibox.containers.orchestrator.ProviderRegistry")
    @patch("aibox.containers.orchestrator.SlotManager")
    def test_start_container_no_provider_specified_for_slot(
        self,
        mock_slot_mgr: Mock,
        _mock_registry: Mock,
        mock_load_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test error when slot exists but no AI provider is configured."""
        from aibox.utils.errors import AiboxError

        config = Config(project=ProjectConfig(name="test"))
        mock_load_config.return_value = config

        # Mock slot that exists but has no AI provider configured
        mock_slot_config = Mock()
        mock_slot_config.get_ai_provider.return_value = None  # No provider configured
        mock_slot_mgr.return_value.get_slot.return_value = mock_slot_config

        orchestrator = ContainerOrchestrator()

        with pytest.raises(AiboxError) as exc_info:
            orchestrator.start_container(
                project_root=tmp_path,
                slot_number=1,
                ai_provider=None,  # No provider specified, should read from slot
            )

        assert "No AI provider specified" in str(exc_info.value)
        assert "aibox slot add" in exc_info.value.suggestion


class TestContainerOrchestratorStopContainer:
    """Tests for stop_container method."""

    @patch("aibox.containers.orchestrator.get_project_storage_dir")
    @patch("aibox.containers.orchestrator.load_config")
    @patch("aibox.containers.orchestrator.ContainerManager")
    @patch("aibox.containers.orchestrator.SlotManager")
    def test_stop_container_success(
        self,
        mock_slot_mgr: Mock,
        mock_container_mgr: Mock,
        mock_load_config: Mock,
        mock_storage_dir: Mock,
        tmp_path: Path,
    ) -> None:
        """Test successful container stop."""
        mock_storage_dir.return_value = tmp_path / ".aibox" / "projects" / "test-hash"
        config = Config(project=ProjectConfig(name="test-project"))
        mock_load_config.return_value = config

        # Mock SlotConfig
        mock_slot_config = Mock()
        mock_slot_config.load.return_value = {"container_name": "aibox-test-project-2"}
        mock_slot_mgr.return_value.get_slot.return_value = mock_slot_config
        mock_slot_mgr.return_value.cleanup_slot = Mock()
        mock_container_mgr.return_value.stop_container = Mock()

        orchestrator = ContainerOrchestrator()
        orchestrator.stop_container(project_root=tmp_path, slot_number=2)

        mock_storage_dir.assert_called_once_with(tmp_path)
        mock_load_config.assert_called_once_with(str(tmp_path))
        mock_container_mgr.return_value.stop_container.assert_called_once_with(
            "aibox-test-project-2"
        )
        # Note: cleanup_slot is no longer called - slot metadata is preserved

    @patch("aibox.containers.orchestrator.load_config")
    @patch("aibox.containers.orchestrator.ContainerManager")
    def test_stop_container_docker_error(
        self,
        mock_container_mgr: Mock,
        mock_load_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test error handling when container stop fails."""
        config = Config(project=ProjectConfig(name="test"))
        mock_load_config.return_value = config

        mock_container_mgr.return_value.stop_container.side_effect = DockerError(
            "Container not found"
        )

        orchestrator = ContainerOrchestrator()

        with patch("aibox.containers.orchestrator.SlotManager"), pytest.raises(DockerError):
            orchestrator.stop_container(project_root=tmp_path, slot_number=1)

    @patch("aibox.containers.orchestrator.get_project_storage_dir")
    @patch("aibox.containers.orchestrator.load_config")
    @patch("aibox.containers.orchestrator.ContainerManager")
    @patch("aibox.containers.orchestrator.SlotManager")
    def test_stop_container_fallback_name_when_no_slot_data(
        self,
        mock_slot_mgr: Mock,
        mock_container_mgr: Mock,
        mock_load_config: Mock,
        mock_storage_dir: Mock,
        tmp_path: Path,
    ) -> None:
        """Test container stop uses fallback name when slot data doesn't have container_name."""
        mock_storage_dir.return_value = tmp_path / ".aibox" / "projects" / "test-hash"
        config = Config(project=ProjectConfig(name="test-project"))
        mock_load_config.return_value = config

        # Mock SlotConfig that returns None (slot doesn't exist or has no data)
        mock_slot_config = Mock()
        mock_slot_config.load.return_value = None  # No slot data
        mock_slot_mgr.return_value.get_slot.return_value = mock_slot_config
        mock_slot_mgr.return_value.cleanup_slot = Mock()
        mock_container_mgr.return_value.stop_container = Mock()

        orchestrator = ContainerOrchestrator()
        orchestrator.stop_container(project_root=tmp_path, slot_number=3)

        # Should use fallback name: aibox-{project_name}-{slot}
        mock_container_mgr.return_value.stop_container.assert_called_once_with(
            "aibox-test-project-3"
        )
        # Note: cleanup_slot is no longer called - slot metadata is preserved


class TestContainerInfo:
    """Tests for ContainerInfo dataclass."""

    def test_container_info_creation(self) -> None:
        """Test ContainerInfo can be created with all fields."""
        info = ContainerInfo(
            container_id="abc123",
            container_name="aibox-test-1",
            slot_number=1,
            ai_provider="claude",
            project_name="test",
        )

        assert info.container_id == "abc123"
        assert info.container_name == "aibox-test-1"
        assert info.slot_number == 1
        assert info.ai_provider == "claude"
        assert info.project_name == "test"


class TestContainerOrchestratorAttachToContainer:
    """Tests for attach_to_container method."""

    @patch("aibox.containers.orchestrator.get_project_storage_dir")
    @patch("aibox.containers.orchestrator.load_config")
    @patch("aibox.containers.orchestrator.ContainerManager")
    @patch("aibox.containers.orchestrator.SlotManager")
    @patch("aibox.containers.orchestrator.ProviderRegistry")
    def test_attach_to_container_with_slot_specified(
        self,
        mock_registry: Mock,
        mock_slot_mgr: Mock,
        mock_container_mgr: Mock,
        mock_load_config: Mock,
        mock_storage_dir: Mock,
        tmp_path: Path,
    ) -> None:
        """Test attaching to container with slot number specified."""
        mock_storage_dir.return_value = tmp_path / ".aibox"
        config = Config(project=ProjectConfig(name="test"))
        mock_load_config.return_value = config

        # Mock slot data
        mock_slot_config = Mock()
        mock_slot_config.load.return_value = {
            "container_name": "aibox-test-2",
            "ai_provider": "claude",
        }
        mock_slot_mgr.return_value.get_slot.return_value = mock_slot_config

        # Mock provider
        mock_provider = Mock()
        mock_provider.get_cli_command.return_value = ["claude"]
        mock_registry.get_provider.return_value = mock_provider

        # Mock attach_interactive to return exit code
        mock_container_mgr.return_value.attach_interactive.return_value = 0

        orchestrator = ContainerOrchestrator()
        exit_code = orchestrator.attach_to_container(
            project_root=tmp_path,
            slot_number=2,
        )

        assert exit_code == 0
        mock_load_config.assert_called_once_with(str(tmp_path))
        mock_slot_mgr.return_value.get_slot.assert_called_once_with(2)
        mock_registry.get_provider.assert_called_once_with("claude")
        mock_container_mgr.return_value.attach_interactive.assert_called_once_with(
            "aibox-test-2", ["claude"]
        )

    @patch("aibox.containers.orchestrator.get_project_storage_dir")
    @patch("aibox.containers.orchestrator.load_config")
    @patch("aibox.containers.orchestrator.ContainerManager")
    @patch("aibox.containers.orchestrator.SlotManager")
    @patch("aibox.containers.orchestrator.ProviderRegistry")
    def test_attach_to_container_auto_find_running_slot(
        self,
        mock_registry: Mock,
        mock_slot_mgr: Mock,
        mock_container_mgr: Mock,
        mock_load_config: Mock,
        mock_storage_dir: Mock,
        tmp_path: Path,
    ) -> None:
        """Test attaching to container without slot specified (finds first running)."""
        mock_storage_dir.return_value = tmp_path / ".aibox"
        config = Config(project=ProjectConfig(name="test"))
        mock_load_config.return_value = config

        # Mock list_slots returning multiple slots
        mock_slot_mgr.return_value.list_slots.return_value = [
            {"slot": 1, "container_name": "aibox-test-1", "ai_provider": "gemini"},
            {"slot": 2, "container_name": "aibox-test-2", "ai_provider": "claude"},
            {"slot": 3, "container_name": "aibox-test-3", "ai_provider": "openai"},
        ]

        # Mock is_container_running: slot 1 stopped, slot 2 running
        def is_running_side_effect(name: str) -> bool:
            return name == "aibox-test-2"

        mock_container_mgr.return_value.is_container_running.side_effect = is_running_side_effect

        # Mock slot 2 data
        mock_slot_config = Mock()
        mock_slot_config.load.return_value = {
            "container_name": "aibox-test-2",
            "ai_provider": "claude",
        }
        mock_slot_mgr.return_value.get_slot.return_value = mock_slot_config

        # Mock provider
        mock_provider = Mock()
        mock_provider.get_cli_command.return_value = ["claude"]
        mock_registry.get_provider.return_value = mock_provider

        mock_container_mgr.return_value.attach_interactive.return_value = 0

        orchestrator = ContainerOrchestrator()
        exit_code = orchestrator.attach_to_container(
            project_root=tmp_path,
            slot_number=None,  # Auto-find
        )

        assert exit_code == 0
        # Should have found and attached to slot 2
        mock_slot_mgr.return_value.get_slot.assert_called_once_with(2)
        mock_container_mgr.return_value.attach_interactive.assert_called_once_with(
            "aibox-test-2", ["claude"]
        )

    @patch("aibox.containers.orchestrator.get_project_storage_dir")
    @patch("aibox.containers.orchestrator.load_config")
    @patch("aibox.containers.orchestrator.ContainerManager")
    @patch("aibox.containers.orchestrator.SlotManager")
    def test_attach_to_container_no_running_containers(
        self,
        mock_slot_mgr: Mock,
        mock_container_mgr: Mock,
        mock_load_config: Mock,
        mock_storage_dir: Mock,
        tmp_path: Path,
    ) -> None:
        """Test error when no running containers found for auto-attach."""
        from aibox.utils.errors import SlotNotFoundError

        mock_storage_dir.return_value = tmp_path / ".aibox"
        config = Config(project=ProjectConfig(name="test"))
        mock_load_config.return_value = config

        # Mock list_slots returning slots but none are running
        mock_slot_mgr.return_value.list_slots.return_value = [
            {"slot": 1, "container_name": "aibox-test-1"},
            {"slot": 2, "container_name": "aibox-test-2"},
        ]
        mock_container_mgr.return_value.is_container_running.return_value = False

        orchestrator = ContainerOrchestrator()

        with pytest.raises(SlotNotFoundError) as exc_info:
            orchestrator.attach_to_container(
                project_root=tmp_path,
                slot_number=None,
            )

        assert "No running containers found" in str(exc_info.value)
        assert "aibox start" in exc_info.value.suggestion

    @patch("aibox.containers.orchestrator.Path.home")
    @patch("aibox.containers.orchestrator.get_project_storage_dir")
    @patch("aibox.containers.orchestrator.load_config")
    @patch("aibox.containers.orchestrator.ContainerManager")
    @patch("aibox.containers.orchestrator.SlotManager")
    @patch("aibox.containers.orchestrator.ProviderRegistry")
    def test_attach_to_container_openai_uses_resume_when_session_exists(
        self,
        mock_registry: Mock,
        mock_slot_mgr: Mock,
        mock_container_mgr: Mock,
        mock_load_config: Mock,
        mock_storage_dir: Mock,
        mock_home: Mock,
        tmp_path: Path,
    ) -> None:
        """OpenAI attach uses 'codex resume' when slot has persisted session."""
        mock_storage_dir.return_value = "proj-123"
        mock_home.return_value = tmp_path
        config = Config(project=ProjectConfig(name="test"))
        mock_load_config.return_value = config

        slot_dir = tmp_path / ".aibox" / "projects" / "proj-123" / "slots" / "slot-2" / ".codex"
        slot_dir.mkdir(parents=True, exist_ok=True)
        (slot_dir / "config.json").write_text("session")

        mock_slot_config = Mock()
        mock_slot_config.load.return_value = {
            "container_name": "aibox-test-2",
            "ai_provider": "openai",
        }
        mock_slot_mgr.return_value.get_slot.return_value = mock_slot_config

        mock_provider = Mock()
        mock_provider.name = "openai"
        mock_provider.get_cli_command.return_value = ["codex-wrapper"]
        mock_registry.get_provider.return_value = mock_provider

        mock_container_mgr.return_value.attach_interactive.return_value = 0

        orchestrator = ContainerOrchestrator()
        exit_code = orchestrator.attach_to_container(
            project_root=tmp_path, slot_number=2, resume=True
        )

        assert exit_code == 0
        mock_container_mgr.return_value.attach_interactive.assert_called_once_with(
            "aibox-test-2",
            ["codex", "resume"],
        )

    @patch("aibox.containers.orchestrator.get_project_storage_dir")
    @patch("aibox.containers.orchestrator.load_config")
    @patch("aibox.containers.orchestrator.SlotManager")
    def test_attach_to_container_slot_not_found(
        self,
        mock_slot_mgr: Mock,
        mock_load_config: Mock,
        mock_storage_dir: Mock,
        tmp_path: Path,
    ) -> None:
        """Test error when specified slot doesn't exist."""
        from aibox.utils.errors import SlotNotFoundError

        mock_storage_dir.return_value = tmp_path / ".aibox"
        config = Config(project=ProjectConfig(name="test"))
        mock_load_config.return_value = config

        # Mock slot that doesn't exist
        mock_slot_config = Mock()
        mock_slot_config.load.return_value = None  # No slot data
        mock_slot_mgr.return_value.get_slot.return_value = mock_slot_config

        orchestrator = ContainerOrchestrator()

        with pytest.raises(SlotNotFoundError) as exc_info:
            orchestrator.attach_to_container(
                project_root=tmp_path,
                slot_number=5,
            )

        assert "Slot 5 not found" in str(exc_info.value)
        assert "aibox slot list" in exc_info.value.suggestion


# Note: Config merging tests removed as AI configuration is now slot-level only.
# AI provider is specified when starting containers, not in project config.


class TestContainerOrchestratorImageHash:
    """Tests for image hash generation."""

    def test_generate_image_hash_consistent(self) -> None:
        """Test that hash generation is consistent for same inputs."""
        dockerfile = "FROM debian:bookworm-slim\nRUN echo hello"
        base_image = "debian:bookworm-slim"
        profiles = ["python:3.12", "nodejs:20"]

        hash1 = ContainerOrchestrator._generate_base_image_hash(dockerfile, base_image, profiles)
        hash2 = ContainerOrchestrator._generate_base_image_hash(dockerfile, base_image, profiles)

        assert hash1 == hash2
        assert len(hash1) == 12  # Should be 12 characters

    def test_generate_image_hash_different_dockerfile(self) -> None:
        """Test that different Dockerfiles produce different hashes."""
        base_image = "debian:bookworm-slim"
        profiles = ["python:3.12"]

        hash1 = ContainerOrchestrator._generate_base_image_hash(
            "FROM debian:bookworm-slim\nRUN echo hello", base_image, profiles
        )
        hash2 = ContainerOrchestrator._generate_base_image_hash(
            "FROM debian:bookworm-slim\nRUN echo world", base_image, profiles
        )

        assert hash1 != hash2

    def test_generate_image_hash_different_profiles(self) -> None:
        """Test that different profiles produce different hashes."""
        dockerfile = "FROM debian:bookworm-slim"
        base_image = "debian:bookworm-slim"

        hash1 = ContainerOrchestrator._generate_base_image_hash(
            dockerfile, base_image, ["python:3.12"]
        )
        hash2 = ContainerOrchestrator._generate_base_image_hash(
            dockerfile, base_image, ["python:3.13"]
        )

        assert hash1 != hash2

    def test_generate_image_hash_profile_order_independent(self) -> None:
        """Test that profile order doesn't affect hash (sorted internally)."""
        dockerfile = "FROM debian:bookworm-slim"
        base_image = "debian:bookworm-slim"

        hash1 = ContainerOrchestrator._generate_base_image_hash(
            dockerfile, base_image, ["python:3.12", "nodejs:20"]
        )
        hash2 = ContainerOrchestrator._generate_base_image_hash(
            dockerfile, base_image, ["nodejs:20", "python:3.12"]
        )

        # Hashes should be the same because profiles are sorted
        assert hash1 == hash2

    def test_generate_provider_hash_changes_with_provider_or_base(self) -> None:
        """Provider hash accounts for provider layer and base hash."""
        dockerfile = "FROM base\nRUN npm install -g some-cli"

        hash_provider1 = ContainerOrchestrator._generate_provider_image_hash(
            dockerfile_content=dockerfile, provider_name="claude", base_hash="aaa111"
        )
        hash_provider2 = ContainerOrchestrator._generate_provider_image_hash(
            dockerfile_content=dockerfile, provider_name="gemini", base_hash="aaa111"
        )
        hash_provider3 = ContainerOrchestrator._generate_provider_image_hash(
            dockerfile_content=dockerfile, provider_name="claude", base_hash="bbb222"
        )

        assert hash_provider1 != hash_provider2
        assert hash_provider1 != hash_provider3
