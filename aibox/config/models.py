"""
Pydantic models for aibox configuration.

These models provide type-safe configuration with validation:
- MountConfig: Volume mount configuration
- DockerResourceConfig: Docker resource limits
- DockerConfig: Docker configuration
- ProjectConfig: Project-level settings
- GlobalConfig: Global settings
- Config: Combined configuration (global + project)
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class MountConfig(BaseModel):
    """Configuration for a Docker volume mount."""

    source: str = Field(..., description="Host path to mount")
    target: str = Field(..., description="Container path to mount to")
    mode: Literal["rw", "ro"] = Field(
        default="ro", description="Mount mode: read-write or read-only"
    )

    @field_validator("source")
    @classmethod
    def validate_source_not_empty(cls, v: str) -> str:
        """Ensure source path is not empty."""
        if not v or not v.strip():
            raise ValueError("source path cannot be empty")
        return v.strip()

    @field_validator("target")
    @classmethod
    def validate_target_not_empty(cls, v: str) -> str:
        """Ensure target path is not empty."""
        if not v or not v.strip():
            raise ValueError("target path cannot be empty")
        return v.strip()


class DockerResourceConfig(BaseModel):
    """Docker resource limits configuration."""

    cpus: int = Field(default=2, ge=1, le=32, description="Number of CPUs to allocate")
    memory: str = Field(default="2g", description="Memory limit (e.g., '4g', '2048m')")

    @field_validator("memory")
    @classmethod
    def validate_memory_format(cls, v: str) -> str:
        """Ensure memory is in valid format (e.g., '4g', '2048m')."""
        import re

        if not re.match(r"^\d+[kmg]$", v.lower()):
            raise ValueError(f"memory must be in format like '4g' or '2048m', got '{v}'")
        return v.lower()


class DockerConfig(BaseModel):
    """Docker configuration."""

    base_image: str = Field(default="debian:bookworm-slim", description="Base Docker image to use")
    default_resources: DockerResourceConfig = Field(
        default_factory=DockerResourceConfig, description="Default resource limits"
    )


class ProjectConfig(BaseModel):
    """Project-level configuration."""

    name: str = Field(..., description="Project name")
    profiles: list[str] = Field(default_factory=list, description="List of profiles to enable")
    mounts: list[MountConfig] = Field(default_factory=list, description="Additional volume mounts")
    environment: dict[str, str] = Field(default_factory=dict, description="Environment variables")

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        """Ensure project name is not empty."""
        if not v or not v.strip():
            raise ValueError("project name cannot be empty")
        return v.strip()

    @field_validator("profiles")
    @classmethod
    def validate_profiles_format(cls, v: list[str]) -> list[str]:
        """Ensure profiles are in valid format (name:version or name)."""
        import re

        for profile in v:
            if not re.match(r"^[a-z0-9_-]+(?::[a-z0-9._-]+)?$", profile.lower()):
                raise ValueError(
                    f"profile must be in format 'name' or 'name:version', got '{profile}'"
                )
        return [p.lower() for p in v]


class GlobalConfig(BaseModel):
    """Global configuration."""

    version: str = Field(default="1.0", description="Config file version")
    docker: DockerConfig = Field(default_factory=DockerConfig, description="Docker configuration")


class Config(BaseModel):
    """Combined configuration (global + project)."""

    global_config: GlobalConfig = Field(
        default_factory=GlobalConfig, description="Global configuration"
    )
    project: ProjectConfig = Field(..., description="Project configuration")

    def get_profiles(self) -> list[str]:
        """Get the list of enabled profiles."""
        return self.project.profiles

    def get_all_environment(self) -> dict[str, str]:
        """Get all environment variables."""
        return self.project.environment.copy()
