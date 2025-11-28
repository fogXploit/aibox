"""Unit tests for profile models."""

import pytest
from pydantic import ValidationError

from aibox.profiles.models import ProfileDefinition


class TestProfileDefinition:
    """Tests for ProfileDefinition model."""

    def test_valid_profile_definition(self) -> None:
        """Test creating a valid profile definition."""
        profile = ProfileDefinition(
            name="python",
            description="Python development",
            versions=["3.11", "3.12"],
            default_version="3.12",
            package_manager="pip",
            system_dependencies=["python3-dev"],
            env_vars={"PYTHON_VERSION": "${VERSION}"},
            docker_layers=["RUN apt-get install -y python3"],
        )

        assert profile.name == "python"
        assert profile.description == "Python development"
        assert profile.versions == ["3.11", "3.12"]
        assert profile.default_version == "3.12"
        assert profile.package_manager == "pip"
        assert "python3-dev" in profile.system_dependencies

    def test_profile_definition_defaults(self) -> None:
        """Test profile definition with default values."""
        profile = ProfileDefinition(
            name="minimal", description="Minimal profile", versions=["1.0"], default_version="1.0"
        )

        assert profile.package_manager is None
        assert profile.system_dependencies == []
        assert profile.install_commands == []
        assert profile.env_vars == {}
        assert profile.docker_layers == []
        assert profile.post_install == []

    def test_profile_name_validation_empty(self) -> None:
        """Test that empty profile name fails validation."""
        with pytest.raises(ValidationError):
            ProfileDefinition(name="", description="Test", versions=["1.0"], default_version="1.0")

    def test_profile_name_validation_format(self) -> None:
        """Test that invalid name format fails validation."""
        with pytest.raises(ValidationError):
            ProfileDefinition(
                name="Invalid Name",  # Contains space and capital
                description="Test",
                versions=["1.0"],
                default_version="1.0",
            )

        with pytest.raises(ValidationError):
            ProfileDefinition(
                name="invalid_name",  # Contains underscore
                description="Test",
                versions=["1.0"],
                default_version="1.0",
            )

    def test_profile_name_validation_valid_formats(self) -> None:
        """Test that valid name formats pass validation."""
        # Lowercase alphanumeric
        profile1 = ProfileDefinition(
            name="python", description="Test", versions=["1.0"], default_version="1.0"
        )
        assert profile1.name == "python"

        # With hyphens
        profile2 = ProfileDefinition(
            name="node-js", description="Test", versions=["1.0"], default_version="1.0"
        )
        assert profile2.name == "node-js"

        # With numbers
        profile3 = ProfileDefinition(
            name="python3", description="Test", versions=["1.0"], default_version="1.0"
        )
        assert profile3.name == "python3"

    def test_default_version_not_in_versions(self) -> None:
        """Test that default_version must be in versions list."""
        with pytest.raises(ValidationError):
            ProfileDefinition(
                name="test",
                description="Test",
                versions=["1.0", "2.0"],
                default_version="3.0",  # Not in versions list
            )

    def test_versions_cannot_be_empty(self) -> None:
        """Test that versions list cannot be empty."""
        with pytest.raises(ValidationError):
            ProfileDefinition(name="test", description="Test", versions=[], default_version="1.0")

    def test_get_version_default(self) -> None:
        """Test getting default version."""
        profile = ProfileDefinition(
            name="test", description="Test", versions=["1.0", "2.0"], default_version="2.0"
        )

        assert profile.get_version() == "2.0"
        assert profile.get_version(None) == "2.0"

    def test_get_version_requested(self) -> None:
        """Test getting requested version."""
        profile = ProfileDefinition(
            name="test", description="Test", versions=["1.0", "2.0", "3.0"], default_version="2.0"
        )

        assert profile.get_version("1.0") == "1.0"
        assert profile.get_version("3.0") == "3.0"

    def test_get_version_invalid(self) -> None:
        """Test getting invalid version raises error."""
        profile = ProfileDefinition(
            name="test", description="Test", versions=["1.0", "2.0"], default_version="1.0"
        )

        with pytest.raises(ValueError, match="not available"):
            profile.get_version("3.0")

    def test_get_env_vars_with_version(self) -> None:
        """Test environment variable version substitution."""
        profile = ProfileDefinition(
            name="python",
            description="Python",
            versions=["3.11", "3.12"],
            default_version="3.12",
            env_vars={
                "VERSION": "${VERSION}",
                "PYTHON_VERSION": "${PYTHON_VERSION}",
                "PATH": "/opt/python/${VERSION}/bin:$PATH",
            },
        )

        env = profile.get_env_vars_with_version("3.11")

        assert env["VERSION"] == "3.11"
        assert env["PYTHON_VERSION"] == "3.11"
        assert env["PATH"] == "/opt/python/3.11/bin:$PATH"

    def test_get_docker_layers_with_version(self) -> None:
        """Test Docker layer version substitution."""
        profile = ProfileDefinition(
            name="python",
            description="Python",
            versions=["3.11", "3.12"],
            default_version="3.12",
            docker_layers=[
                "RUN wget python-${VERSION}.tar.gz",
                "RUN tar xf python-${PYTHON_VERSION}.tar.gz",
            ],
        )

        layers = profile.get_docker_layers_with_version("3.11")

        assert layers[0] == "RUN wget python-3.11.tar.gz"
        assert layers[1] == "RUN tar xf python-3.11.tar.gz"
