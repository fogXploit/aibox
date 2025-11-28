"""
Pydantic models for profile definitions.

Profiles define language environments (Python, Node.js, Go, etc.) with:
- Available versions
- System dependencies
- Installation commands
- Environment variables
- Docker layers
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ProfileDefinition(BaseModel):
    """Definition of a language/tool profile loaded from YAML."""

    name: str = Field(..., description="Profile name (e.g., 'python', 'nodejs')")
    description: str = Field(..., description="Human-readable description")
    versions: list[str] = Field(..., description="Available versions (e.g., ['3.11', '3.12'])")
    default_version: str = Field(..., description="Default version if not specified")
    package_manager: str | None = Field(
        default=None, description="Package manager (e.g., 'pip', 'npm', 'cargo')"
    )
    system_dependencies: list[str] = Field(
        default_factory=list, description="System packages to install via apt-get"
    )
    install_commands: list[str] = Field(
        default_factory=list, description="Commands to run during installation"
    )
    env_vars: dict[str, str] = Field(
        default_factory=dict, description="Environment variables to set"
    )
    docker_layers: list[str] = Field(
        default_factory=list, description="Dockerfile RUN commands (each becomes a layer)"
    )
    post_install: list[str] = Field(
        default_factory=list, description="Commands to run after profile installation"
    )

    @field_validator("name")
    @classmethod
    def validate_name_format(cls, v: str) -> str:
        """Ensure profile name is lowercase alphanumeric with hyphens."""
        if not v:
            raise ValueError("profile name cannot be empty")

        # Check format
        import re

        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError(f"profile name '{v}' must be lowercase alphanumeric with hyphens only")

        return v

    @field_validator("default_version")
    @classmethod
    def validate_default_version_exists(cls, v: str, info: Any) -> str:
        """Ensure default version is in the versions list."""
        if "versions" in info.data:
            versions = info.data["versions"]
            if v not in versions:
                raise ValueError(
                    f"default_version '{v}' must be one of the available versions: {versions}"
                )
        return v

    @field_validator("versions")
    @classmethod
    def validate_versions_not_empty(cls, v: list[str]) -> list[str]:
        """Ensure at least one version is provided."""
        if not v:
            raise ValueError("at least one version must be specified")
        return v

    def get_version(self, requested_version: str | None = None) -> str:
        """
        Get version to use, falling back to default.

        Args:
            requested_version: Requested version, or None for default

        Returns:
            Version string to use

        Raises:
            ValueError: If requested version is not available
        """
        if requested_version is None:
            return self.default_version

        if requested_version not in self.versions:
            raise ValueError(
                f"Version '{requested_version}' not available for {self.name}. "
                f"Available: {', '.join(self.versions)}"
            )

        return requested_version

    def get_env_vars_with_version(self, version: str) -> dict[str, str]:
        """
        Get environment variables with version placeholders replaced.

        Args:
            version: Version string to use for replacements

        Returns:
            Dictionary with ${VERSION} replaced by actual version
        """
        env = {}
        for key, value in self.env_vars.items():
            # Replace version placeholders
            replaced = value.replace("${VERSION}", version)
            replaced = replaced.replace(f"${{{self.name.upper()}_VERSION}}", version)
            env[key] = replaced

        return env

    def get_docker_layers_with_version(self, version: str) -> list[str]:
        """
        Get Docker layers with version placeholders replaced.

        Args:
            version: Version string to use for replacements

        Returns:
            List of Docker RUN commands with version substituted
        """
        layers = []
        for layer in self.docker_layers:
            # Replace version placeholders
            replaced = layer.replace("${VERSION}", version)
            replaced = replaced.replace(f"${{{self.name.upper()}_VERSION}}", version)
            layers.append(replaced)

        return layers

    def get_post_install_with_version(self, version: str) -> list[str]:
        """
        Get post-install commands with version placeholders replaced.

        Args:
            version: Version string to use for replacements

        Returns:
            List of post-install commands with version substituted
        """
        commands = []
        for cmd in self.post_install:
            # Replace version placeholders
            replaced = cmd.replace("${VERSION}", version)
            replaced = replaced.replace(f"${{{self.name.upper()}_VERSION}}", version)
            commands.append(replaced)

        return commands
