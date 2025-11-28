"""
Configuration loader for aibox.

Functions for loading, saving, and merging YAML configuration files:
- load_global_config: Load global config from ~/.aibox/config.yml
- load_project_config: Load project config from .aibox/config.yml
- merge_configs: Merge project config over global config
- save_config: Save configuration to YAML file
"""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from aibox.config.models import Config, GlobalConfig, ProjectConfig
from aibox.utils.errors import ConfigNotFoundError, InvalidConfigError


def expand_path(path: str) -> Path:
    """
    Expand user home directory and resolve path.

    Args:
        path: Path string that may contain ~ or relative components

    Returns:
        Resolved absolute Path
    """
    return Path(path).expanduser().resolve()


def get_global_config_path() -> Path:
    """Get the path to the global config file."""
    return expand_path("~/.aibox/config.yml")


def get_aibox_ref_path(project_dir: str | Path | None = None) -> Path:
    """
    Get path to .aibox-ref file in project directory.

    The .aibox-ref file contains the storage directory name (hash) that
    points to the actual project configuration in ~/.aibox/projects/<hash>/.

    Args:
        project_dir: Project directory (defaults to current directory)

    Returns:
        Path to <project>/.aibox/.aibox-ref
    """
    if project_dir is None:
        base_path = Path(os.getcwd())
    elif isinstance(project_dir, Path):
        base_path = project_dir
    else:
        base_path = expand_path(project_dir)
    return base_path / ".aibox" / ".aibox-ref"


def save_aibox_ref(project_dir: str | Path, storage_dir_name: str) -> None:
    """
    Save .aibox-ref file containing storage directory hash.

    Creates the .aibox directory if it doesn't exist and writes the
    storage directory name (e.g., "myproject-abc123") to .aibox-ref.

    Args:
        project_dir: Project directory
        storage_dir_name: Storage directory name (e.g., "myproject-abc123")
    """
    ref_path = get_aibox_ref_path(project_dir)
    ref_path.parent.mkdir(parents=True, exist_ok=True)
    ref_path.write_text(storage_dir_name)


def load_aibox_ref(project_dir: str | Path | None = None) -> str | None:
    """
    Load storage directory name from .aibox-ref file.

    Args:
        project_dir: Project directory (defaults to current directory)

    Returns:
        Storage directory name, or None if file doesn't exist
    """
    ref_path = get_aibox_ref_path(project_dir)
    if not ref_path.exists():
        return None
    return ref_path.read_text().strip()


def get_project_config_path(project_dir: str | Path | None = None) -> Path:
    """
    Get path to project config in ~/.aibox/projects/<hash>/config.yml.

    This uses the centralized storage directory, not the project directory.
    The project directory only contains .aibox/.aibox-ref pointing to the hash.

    Args:
        project_dir: Project directory (defaults to current directory)

    Returns:
        Path to project config file in centralized storage
    """
    from aibox.utils.hash import get_project_storage_dir

    if project_dir is None:
        project_dir = Path(os.getcwd())
    elif not isinstance(project_dir, Path):
        project_dir = expand_path(project_dir)

    storage_dir = get_project_storage_dir(project_dir)
    return Path.home() / ".aibox" / "projects" / storage_dir / "config.yml"


def create_default_global_config() -> GlobalConfig:
    """Create a default global configuration."""
    return GlobalConfig()


def create_default_project_config(name: str) -> ProjectConfig:
    """
    Create a default project configuration.

    Args:
        name: Project name

    Returns:
        Default ProjectConfig
    """
    return ProjectConfig(name=name)


def load_yaml_file(path: Path) -> dict[str, Any]:
    """
    Load and parse a YAML file.

    Args:
        path: Path to YAML file

    Returns:
        Parsed YAML as dictionary

    Raises:
        ConfigNotFoundError: If file doesn't exist
        InvalidConfigError: If YAML is invalid
    """
    if not path.exists():
        raise ConfigNotFoundError(
            message=f"Configuration file not found: {path}",
            suggestion=f"Create a config file at {path} or run 'aibox init' to create defaults",
        )

    try:
        with open(path) as f:
            data = yaml.safe_load(f)
            if data is None:
                return {}
            if not isinstance(data, dict):
                raise InvalidConfigError(
                    message=f"Invalid YAML in {path}: expected a dictionary",
                    suggestion="Ensure the YAML file contains a valid configuration structure",
                )
            return data
    except yaml.YAMLError as e:
        raise InvalidConfigError(
            message=f"Failed to parse YAML in {path}: {e}",
            suggestion="Check the YAML syntax and ensure it's valid",
        ) from e
    except OSError as e:
        raise InvalidConfigError(
            message=f"Failed to read config file {path}: {e}",
            suggestion="Check file permissions and ensure the file is readable",
        ) from e


def save_yaml_file(path: Path, data: dict[str, Any]) -> None:
    """
    Save data to a YAML file.

    Args:
        path: Path to save to
        data: Dictionary to save as YAML

    Raises:
        InvalidConfigError: If save fails
    """
    try:
        # Create parent directory if it doesn't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
    except OSError as e:
        raise InvalidConfigError(
            message=f"Failed to write config file {path}: {e}",
            suggestion="Check file permissions and ensure the directory is writable",
        ) from e


def load_global_config(create_if_missing: bool = False) -> GlobalConfig:
    """
    Load global configuration from ~/.aibox/config.yml.

    Args:
        create_if_missing: If True, create default config if file doesn't exist

    Returns:
        GlobalConfig instance

    Raises:
        ConfigNotFoundError: If config file doesn't exist and create_if_missing is False
        InvalidConfigError: If config is invalid
    """
    config_path = get_global_config_path()

    if not config_path.exists():
        if create_if_missing:
            config = create_default_global_config()
            save_global_config(config)
            return config
        else:
            raise ConfigNotFoundError(
                message=f"Global configuration not found at {config_path}",
                suggestion="Run 'aibox init' to create a default configuration",
            )

    data = load_yaml_file(config_path)

    try:
        return GlobalConfig(**data)
    except ValidationError as e:
        raise InvalidConfigError(
            message=f"Invalid global configuration in {config_path}",
            suggestion=f"Fix the validation errors:\n{e}",
        ) from e


def save_global_config(config: GlobalConfig) -> None:
    """
    Save global configuration to ~/.aibox/config.yml.

    Args:
        config: GlobalConfig to save

    Raises:
        InvalidConfigError: If save fails
    """
    config_path = get_global_config_path()
    data = config.model_dump(mode="json", exclude_none=True)
    save_yaml_file(config_path, data)


def load_project_config(
    project_dir: str | Path | None = None, create_if_missing: bool = False
) -> ProjectConfig:
    """
    Load project configuration from ~/.aibox/projects/<hash>/config.yml.

    Args:
        project_dir: Project directory (defaults to current directory)
        create_if_missing: If True, create default config if file doesn't exist

    Returns:
        ProjectConfig instance

    Raises:
        ConfigNotFoundError: If config file doesn't exist and create_if_missing is False
        InvalidConfigError: If config is invalid
    """
    config_path = get_project_config_path(project_dir)

    if not config_path.exists():
        if create_if_missing:
            # Get project name from actual project directory, not config path
            if project_dir is None:
                actual_project_dir = Path(os.getcwd())
            elif isinstance(project_dir, Path):
                actual_project_dir = project_dir
            else:
                actual_project_dir = expand_path(project_dir)

            project_name = actual_project_dir.name
            config = create_default_project_config(project_name)
            save_project_config(config, project_dir)
            return config
        else:
            raise ConfigNotFoundError(
                message=f"Project configuration not found at {config_path}",
                suggestion="Run 'aibox init' in the project directory to create a configuration",
            )

    data = load_yaml_file(config_path)

    try:
        return ProjectConfig(**data)
    except ValidationError as e:
        raise InvalidConfigError(
            message=f"Invalid project configuration in {config_path}",
            suggestion=f"Fix the validation errors:\n{e}",
        ) from e


def save_project_config(config: ProjectConfig, project_dir: str | Path | None = None) -> None:
    """
    Save project configuration to ~/.aibox/projects/<hash>/config.yml.

    Args:
        config: ProjectConfig to save
        project_dir: Project directory (defaults to current directory)

    Raises:
        InvalidConfigError: If save fails
    """
    config_path = get_project_config_path(project_dir)
    data = config.model_dump(mode="json", exclude_none=True)
    save_yaml_file(config_path, data)


def merge_configs(global_config: GlobalConfig, project_config: ProjectConfig) -> Config:
    """
    Merge project configuration over global configuration.

    Project settings take precedence over global settings.

    Args:
        global_config: Global configuration
        project_config: Project configuration

    Returns:
        Combined Config instance
    """
    return Config(global_config=global_config, project=project_config)


def load_config(project_dir: str | None = None, create_if_missing: bool = False) -> Config:
    """
    Load and merge global and project configurations.

    Args:
        project_dir: Project directory (defaults to current directory)
        create_if_missing: If True, create default configs if they don't exist

    Returns:
        Combined Config instance

    Raises:
        ConfigNotFoundError: If configs don't exist and create_if_missing is False
        InvalidConfigError: If configs are invalid
    """
    global_config = load_global_config(create_if_missing=create_if_missing)
    project_config = load_project_config(
        project_dir=project_dir, create_if_missing=create_if_missing
    )

    return merge_configs(global_config, project_config)
