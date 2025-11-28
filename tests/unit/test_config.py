"""
Unit tests for aibox configuration system.

Tests cover:
- Pydantic model validation
- YAML loading and parsing
- Configuration merging
- Default value handling
- Error cases
- Path expansion
"""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from aibox.config.loader import (
    create_default_global_config,
    create_default_project_config,
    expand_path,
    get_aibox_ref_path,
    load_aibox_ref,
    load_config,
    load_global_config,
    load_project_config,
    load_yaml_file,
    merge_configs,
    save_aibox_ref,
    save_global_config,
    save_project_config,
    save_yaml_file,
)
from aibox.config.models import (
    Config,
    DockerConfig,
    DockerResourceConfig,
    GlobalConfig,
    MountConfig,
    ProjectConfig,
)
from aibox.utils.errors import ConfigNotFoundError, InvalidConfigError


class TestMountConfig:
    """Tests for MountConfig model."""

    def test_valid_mount_config(self) -> None:
        """Test creating a valid mount configuration."""
        mount = MountConfig(source="/host/path", target="/container/path", mode="rw")
        assert mount.source == "/host/path"
        assert mount.target == "/container/path"
        assert mount.mode == "rw"

    def test_mount_config_default_mode(self) -> None:
        """Test mount configuration with default mode."""
        mount = MountConfig(source="/host/path", target="/container/path")
        assert mount.mode == "ro"

    def test_mount_config_invalid_mode(self) -> None:
        """Test mount configuration with invalid mode."""
        with pytest.raises(ValidationError):
            MountConfig(source="/host/path", target="/container/path", mode="invalid")  # type: ignore

    def test_mount_config_empty_source(self) -> None:
        """Test mount configuration with empty source."""
        with pytest.raises(ValidationError):
            MountConfig(source="", target="/container/path")

    def test_mount_config_empty_target(self) -> None:
        """Test mount configuration with empty target."""
        with pytest.raises(ValidationError):
            MountConfig(source="/host/path", target="")

    def test_mount_config_strips_whitespace(self) -> None:
        """Test mount configuration strips whitespace."""
        mount = MountConfig(source="  /host/path  ", target="  /container/path  ")
        assert mount.source == "/host/path"
        assert mount.target == "/container/path"


class TestDockerResourceConfig:
    """Tests for DockerResourceConfig model."""

    def test_valid_docker_resource_config(self) -> None:
        """Test creating valid Docker resource configuration."""
        resources = DockerResourceConfig(cpus=4, memory="8g")
        assert resources.cpus == 4
        assert resources.memory == "8g"

    def test_docker_resource_config_defaults(self) -> None:
        """Test Docker resource configuration defaults."""
        resources = DockerResourceConfig()
        assert resources.cpus == 2
        assert resources.memory == "2g"

    def test_docker_resource_config_invalid_cpus(self) -> None:
        """Test Docker resource configuration with invalid CPU count."""
        with pytest.raises(ValidationError):
            DockerResourceConfig(cpus=0)
        with pytest.raises(ValidationError):
            DockerResourceConfig(cpus=100)

    def test_docker_resource_config_invalid_memory_format(self) -> None:
        """Test Docker resource configuration with invalid memory format."""
        with pytest.raises(ValidationError):
            DockerResourceConfig(memory="invalid")
        with pytest.raises(ValidationError):
            DockerResourceConfig(memory="100")

    def test_docker_resource_config_memory_formats(self) -> None:
        """Test Docker resource configuration accepts various memory formats."""
        assert DockerResourceConfig(memory="2048m").memory == "2048m"
        assert DockerResourceConfig(memory="4g").memory == "4g"
        assert DockerResourceConfig(memory="1024k").memory == "1024k"


class TestDockerConfig:
    """Tests for DockerConfig model."""

    def test_valid_docker_config(self) -> None:
        """Test creating valid Docker configuration."""
        docker = DockerConfig(
            base_image="debian:bookworm-slim",
            default_resources=DockerResourceConfig(cpus=4, memory="8g"),
        )
        assert docker.base_image == "debian:bookworm-slim"
        assert docker.default_resources.cpus == 4
        assert docker.default_resources.memory == "8g"

    def test_docker_config_defaults(self) -> None:
        """Test Docker configuration defaults."""
        docker = DockerConfig()
        assert docker.base_image == "debian:bookworm-slim"
        assert docker.default_resources.cpus == 2
        assert docker.default_resources.memory == "2g"


class TestProjectConfig:
    """Tests for ProjectConfig model."""

    def test_valid_project_config(self) -> None:
        """Test creating valid project configuration."""
        project = ProjectConfig(
            name="my-project",
            profiles=["python:3.12", "nodejs:20"],
            mounts=[MountConfig(source="/host", target="/container")],
            environment={"VAR": "value"},
        )
        assert project.name == "my-project"
        assert project.profiles == ["python:3.12", "nodejs:20"]
        assert len(project.mounts) == 1
        assert project.environment == {"VAR": "value"}

    def test_project_config_empty_name(self) -> None:
        """Test project configuration with empty name."""
        with pytest.raises(ValidationError):
            ProjectConfig(name="")

    def test_project_config_invalid_profile_format(self) -> None:
        """Test project configuration with invalid profile format."""
        with pytest.raises(ValidationError):
            ProjectConfig(name="test", profiles=["invalid profile"])

    def test_project_config_profile_normalization(self) -> None:
        """Test project configuration normalizes profiles to lowercase."""
        project = ProjectConfig(name="test", profiles=["Python:3.12", "NODEJS:20"])
        assert project.profiles == ["python:3.12", "nodejs:20"]

    def test_project_config_defaults(self) -> None:
        """Test project configuration with defaults."""
        project = ProjectConfig(name="test")
        assert project.profiles == []
        assert project.mounts == []
        assert project.environment == {}


class TestGlobalConfig:
    """Tests for GlobalConfig model."""

    def test_valid_global_config(self) -> None:
        """Test creating valid global configuration."""
        config = GlobalConfig(version="1.0", docker=DockerConfig())
        assert config.version == "1.0"
        assert config.docker.base_image == "debian:bookworm-slim"

    def test_global_config_defaults(self) -> None:
        """Test global configuration defaults."""
        config = GlobalConfig()
        assert config.version == "1.0"
        assert config.docker.base_image == "debian:bookworm-slim"


class TestConfig:
    """Tests for combined Config model."""

    def test_valid_config(self) -> None:
        """Test creating valid combined configuration."""
        config = Config(global_config=GlobalConfig(), project=ProjectConfig(name="test"))
        assert config.global_config.version == "1.0"
        assert config.project.name == "test"

    def test_config_get_profiles(self) -> None:
        """Test getting profiles."""
        config = Config(
            global_config=GlobalConfig(),
            project=ProjectConfig(name="test", profiles=["python:3.12"]),
        )
        assert config.get_profiles() == ["python:3.12"]

    def test_config_get_all_environment(self) -> None:
        """Test getting all environment variables."""
        config = Config(
            global_config=GlobalConfig(),
            project=ProjectConfig(name="test", environment={"VAR": "value"}),
        )
        env = config.get_all_environment()
        assert env == {"VAR": "value"}


class TestPathExpansion:
    """Tests for path expansion utilities."""

    def test_expand_path_with_tilde(self) -> None:
        """Test path expansion with tilde."""
        expanded = expand_path("~/.aibox")
        assert "~" not in str(expanded)
        assert expanded.is_absolute()

    def test_expand_path_absolute(self) -> None:
        """Test path expansion with absolute path."""
        expanded = expand_path("/absolute/path")
        assert str(expanded) == "/absolute/path"

    def test_expand_path_relative(self) -> None:
        """Test path expansion with relative path."""
        expanded = expand_path("relative/path")
        assert expanded.is_absolute()


class TestYAMLOperations:
    """Tests for YAML loading and saving."""

    def test_load_yaml_file_valid(self, tmp_path: Path) -> None:
        """Test loading valid YAML file."""
        yaml_file = tmp_path / "config.yml"
        data = {"key": "value", "number": 42}
        with open(yaml_file, "w") as f:
            yaml.safe_dump(data, f)

        loaded = load_yaml_file(yaml_file)
        assert loaded == data

    def test_load_yaml_file_not_found(self, tmp_path: Path) -> None:
        """Test loading non-existent YAML file."""
        yaml_file = tmp_path / "nonexistent.yml"
        with pytest.raises(ConfigNotFoundError):
            load_yaml_file(yaml_file)

    def test_load_yaml_file_invalid_yaml(self, tmp_path: Path) -> None:
        """Test loading invalid YAML file."""
        yaml_file = tmp_path / "invalid.yml"
        with open(yaml_file, "w") as f:
            f.write("{ invalid yaml [")

        with pytest.raises(InvalidConfigError):
            load_yaml_file(yaml_file)

    def test_load_yaml_file_empty(self, tmp_path: Path) -> None:
        """Test loading empty YAML file."""
        yaml_file = tmp_path / "empty.yml"
        yaml_file.touch()

        loaded = load_yaml_file(yaml_file)
        assert loaded == {}

    def test_save_yaml_file(self, tmp_path: Path) -> None:
        """Test saving YAML file."""
        yaml_file = tmp_path / "config.yml"
        data = {"key": "value", "number": 42}

        save_yaml_file(yaml_file, data)

        assert yaml_file.exists()
        with open(yaml_file) as f:
            loaded = yaml.safe_load(f)
        assert loaded == data

    def test_save_yaml_file_creates_directory(self, tmp_path: Path) -> None:
        """Test saving YAML file creates parent directories."""
        yaml_file = tmp_path / "nested" / "dir" / "config.yml"
        data = {"key": "value"}

        save_yaml_file(yaml_file, data)

        assert yaml_file.exists()
        assert yaml_file.parent.exists()


class TestGlobalConfigLoading:
    """Tests for global configuration loading."""

    def test_load_global_config_valid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test loading valid global configuration."""
        config_file = tmp_path / "config.yml"
        data = {
            "version": "1.0",
            "docker": {
                "base_image": "debian:bookworm-slim",
                "default_resources": {"cpus": 4, "memory": "8g"},
            },
        }
        with open(config_file, "w") as f:
            yaml.safe_dump(data, f)

        monkeypatch.setattr("aibox.config.loader.get_global_config_path", lambda: config_file)

        config = load_global_config()
        assert config.version == "1.0"
        assert config.docker.default_resources.cpus == 4
        assert config.docker.default_resources.memory == "8g"

    def test_load_global_config_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test loading non-existent global configuration."""
        config_file = tmp_path / "nonexistent.yml"
        monkeypatch.setattr("aibox.config.loader.get_global_config_path", lambda: config_file)

        with pytest.raises(ConfigNotFoundError):
            load_global_config()

    def test_load_global_config_create_if_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test loading global configuration with create_if_missing."""
        config_file = tmp_path / "config.yml"
        monkeypatch.setattr("aibox.config.loader.get_global_config_path", lambda: config_file)

        config = load_global_config(create_if_missing=True)
        assert config.version == "1.0"
        assert config_file.exists()

    def test_save_global_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test saving global configuration."""
        config_file = tmp_path / "config.yml"
        monkeypatch.setattr("aibox.config.loader.get_global_config_path", lambda: config_file)

        config = GlobalConfig()
        save_global_config(config)

        assert config_file.exists()
        with open(config_file) as f:
            data = yaml.safe_load(f)
        assert data["version"] == "1.0"


class TestProjectConfigLoading:
    """Tests for project configuration loading."""

    def test_load_project_config_valid(self, tmp_path: Path) -> None:
        """Test loading valid project configuration."""
        from aibox.utils.hash import get_project_storage_dir

        # Get storage directory for this project
        storage_dir = get_project_storage_dir(tmp_path)
        config_file = Path.home() / ".aibox" / "projects" / storage_dir / "config.yml"
        config_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "name": "test-project",
            "profiles": ["python:3.12"],
            "environment": {"VAR": "value"},
        }
        with open(config_file, "w") as f:
            yaml.safe_dump(data, f)

        config = load_project_config(str(tmp_path))
        assert config.name == "test-project"
        assert config.profiles == ["python:3.12"]
        assert config.environment == {"VAR": "value"}

    def test_load_project_config_not_found(self, tmp_path: Path) -> None:
        """Test loading non-existent project configuration."""
        with pytest.raises(ConfigNotFoundError):
            load_project_config(str(tmp_path))

    def test_load_project_config_create_if_missing(self, tmp_path: Path) -> None:
        """Test loading project configuration with create_if_missing."""
        from aibox.utils.hash import get_project_storage_dir

        config = load_project_config(str(tmp_path), create_if_missing=True)
        assert config.name == tmp_path.name

        # Check config is in centralized location
        storage_dir = get_project_storage_dir(tmp_path)
        config_file = Path.home() / ".aibox" / "projects" / storage_dir / "config.yml"
        assert config_file.exists()

    def test_save_project_config(self, tmp_path: Path) -> None:
        """Test saving project configuration."""
        from aibox.utils.hash import get_project_storage_dir

        config = ProjectConfig(name="test-project", profiles=["python:3.12"])
        save_project_config(config, str(tmp_path))

        # Check config is saved to centralized location
        storage_dir = get_project_storage_dir(tmp_path)
        config_file = Path.home() / ".aibox" / "projects" / storage_dir / "config.yml"
        assert config_file.exists()
        with open(config_file) as f:
            data = yaml.safe_load(f)
        assert data["name"] == "test-project"
        assert data["profiles"] == ["python:3.12"]


class TestConfigMerging:
    """Tests for configuration merging."""

    def test_merge_configs(self) -> None:
        """Test merging global and project configurations."""
        global_config = GlobalConfig()
        project_config = ProjectConfig(name="test")

        config = merge_configs(global_config, project_config)
        assert config.global_config.version == "1.0"
        assert config.project.name == "test"

    def test_load_config_full_workflow(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test full configuration loading workflow."""
        from aibox.utils.hash import get_project_storage_dir

        # Create global config
        global_config_file = tmp_path / "global.yml"
        global_data = {
            "version": "1.0",
            "docker": {"base_image": "debian:bookworm-slim"},
        }
        with open(global_config_file, "w") as f:
            yaml.safe_dump(global_data, f)

        # Create project directory
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create project config in centralized location
        storage_dir = get_project_storage_dir(project_dir)
        project_config_file = Path.home() / ".aibox" / "projects" / storage_dir / "config.yml"
        project_config_file.parent.mkdir(parents=True, exist_ok=True)
        project_data = {
            "name": "test-project",
            "profiles": ["python:3.12"],
        }
        with open(project_config_file, "w") as f:
            yaml.safe_dump(project_data, f)

        # Mock global config path
        monkeypatch.setattr(
            "aibox.config.loader.get_global_config_path", lambda: global_config_file
        )

        # Load merged config
        config = load_config(str(project_dir))
        assert config.global_config.version == "1.0"
        assert config.project.name == "test-project"
        assert config.project.profiles == ["python:3.12"]


class TestDefaultConfigs:
    """Tests for default configuration creation."""

    def test_create_default_global_config(self) -> None:
        """Test creating default global configuration."""
        config = create_default_global_config()
        assert config.version == "1.0"
        assert config.docker.base_image == "debian:bookworm-slim"

    def test_create_default_project_config(self) -> None:
        """Test creating default project configuration."""
        config = create_default_project_config("test-project")
        assert config.name == "test-project"
        assert config.profiles == []


class TestReferenceFileOperations:
    """Tests for .aibox-ref reference file operations."""

    def test_get_aibox_ref_path(self, tmp_path: Path) -> None:
        """Test getting .aibox-ref file path."""
        ref_path = get_aibox_ref_path(tmp_path)
        assert ref_path == tmp_path / ".aibox" / ".aibox-ref"

    def test_get_aibox_ref_path_default_cwd(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting .aibox-ref file path with default current directory."""
        test_dir = Path("/test/directory")
        monkeypatch.setattr("os.getcwd", lambda: str(test_dir))
        ref_path = get_aibox_ref_path()
        assert ref_path == test_dir / ".aibox" / ".aibox-ref"

    def test_save_aibox_ref(self, tmp_path: Path) -> None:
        """Test saving .aibox-ref file."""
        storage_dir = "myproject-abc123"
        save_aibox_ref(tmp_path, storage_dir)

        ref_path = tmp_path / ".aibox" / ".aibox-ref"
        assert ref_path.exists()
        assert ref_path.read_text() == storage_dir

    def test_save_aibox_ref_creates_directory(self, tmp_path: Path) -> None:
        """Test saving .aibox-ref file creates parent directory."""
        project_dir = tmp_path / "nested" / "project"
        storage_dir = "myproject-abc123"

        save_aibox_ref(project_dir, storage_dir)

        ref_path = project_dir / ".aibox" / ".aibox-ref"
        assert ref_path.exists()
        assert ref_path.parent.exists()

    def test_load_aibox_ref_existing(self, tmp_path: Path) -> None:
        """Test loading existing .aibox-ref file."""
        storage_dir = "myproject-abc123"
        ref_path = tmp_path / ".aibox" / ".aibox-ref"
        ref_path.parent.mkdir(parents=True, exist_ok=True)
        ref_path.write_text(storage_dir)

        loaded = load_aibox_ref(tmp_path)
        assert loaded == storage_dir

    def test_load_aibox_ref_not_found(self, tmp_path: Path) -> None:
        """Test loading non-existent .aibox-ref file."""
        loaded = load_aibox_ref(tmp_path)
        assert loaded is None

    def test_load_aibox_ref_strips_whitespace(self, tmp_path: Path) -> None:
        """Test loading .aibox-ref file strips whitespace."""
        storage_dir = "myproject-abc123"
        ref_path = tmp_path / ".aibox" / ".aibox-ref"
        ref_path.parent.mkdir(parents=True, exist_ok=True)
        ref_path.write_text(f"  {storage_dir}  \n")

        loaded = load_aibox_ref(tmp_path)
        assert loaded == storage_dir
