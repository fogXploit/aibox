"""Unit tests for profile loader."""

from pathlib import Path

import pytest

from aibox.profiles.loader import ProfileLoader
from aibox.utils.errors import InvalidProfileError, ProfileNotFoundError


class TestProfileLoader:
    """Tests for ProfileLoader class."""

    def test_init_default_directory(self) -> None:
        """Test initialization with default directory."""
        loader = ProfileLoader()
        assert loader.profiles_dir.name == "definitions"
        assert loader.profiles_dir.exists()

    def test_init_custom_directory(self, tmp_path: Path) -> None:
        """Test initialization with custom directory."""
        custom_dir = tmp_path / "custom_profiles"
        custom_dir.mkdir()

        loader = ProfileLoader(custom_dir)
        assert loader.profiles_dir == custom_dir

    def test_parse_spec_name_only(self) -> None:
        """Test parsing profile spec with name only."""
        loader = ProfileLoader()
        name, version = loader._parse_spec("python")

        assert name == "python"
        assert version is None

    def test_parse_spec_with_version(self) -> None:
        """Test parsing profile spec with version."""
        loader = ProfileLoader()
        name, version = loader._parse_spec("python:3.12")

        assert name == "python"
        assert version == "3.12"

    def test_parse_spec_empty(self) -> None:
        """Test parsing empty spec raises error."""
        loader = ProfileLoader()

        with pytest.raises(InvalidProfileError):
            loader._parse_spec("")

    def test_parse_spec_whitespace(self) -> None:
        """Test parsing spec strips whitespace."""
        loader = ProfileLoader()
        name, version = loader._parse_spec("  python : 3.12  ")

        assert name == "python"
        assert version == "3.12"

    def test_list_profiles_builtin(self) -> None:
        """Test listing built-in profiles."""
        loader = ProfileLoader()
        profiles = loader.list_profiles()

        assert "python" in profiles
        assert "nodejs" in profiles
        assert "go" in profiles
        assert "rust" in profiles
        assert "sudo" in profiles
        assert "git" in profiles

    def test_list_profiles_empty_directory(self, tmp_path: Path) -> None:
        """Test listing profiles from empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        loader = ProfileLoader(empty_dir)
        profiles = loader.list_profiles()

        assert profiles == []

    def test_list_profiles_with_info(self) -> None:
        """Test listing profiles with descriptions."""
        loader = ProfileLoader()
        profiles = loader.list_profiles_with_info()

        assert len(profiles) > 0

        # Check structure
        for profile in profiles:
            assert "name" in profile
            assert "description" in profile
            assert "versions" in profile
            assert "default_version" in profile

    def test_load_builtin_python_profile(self) -> None:
        """Test loading built-in Python profile."""
        loader = ProfileLoader()
        profile, version = loader.load_profile("python")

        assert profile.name == "python"
        assert version == profile.default_version
        assert "3.12" in profile.versions

    def test_load_builtin_sudo_profile(self) -> None:
        """Test loading built-in sudo profile."""
        loader = ProfileLoader()
        profile, version = loader.load_profile("sudo")

        assert profile.name == "sudo"
        assert version == profile.default_version
        assert profile.versions == ["1"]
        assert profile.system_dependencies == ["sudo"]
        assert any("NOPASSWD:ALL" in layer for layer in profile.docker_layers)

    def test_load_builtin_git_profile(self) -> None:
        """Test loading built-in git profile."""
        loader = ProfileLoader()
        profile, version = loader.load_profile("git")

        assert profile.name == "git"
        assert version == profile.default_version
        assert profile.versions == ["latest"]
        assert profile.system_dependencies == ["git"]

    def test_load_python_with_specific_version(self) -> None:
        """Test loading Python profile with specific version."""
        loader = ProfileLoader()
        profile, version = loader.load_profile("python:3.11")

        assert profile.name == "python"
        assert version == "3.11"

    def test_load_python_with_invalid_version(self) -> None:
        """Test loading Python profile with invalid version."""
        loader = ProfileLoader()

        with pytest.raises(InvalidProfileError, match="not available"):
            loader.load_profile("python:2.7")

    def test_load_nonexistent_profile(self) -> None:
        """Test loading non-existent profile."""
        loader = ProfileLoader()

        with pytest.raises(ProfileNotFoundError):
            loader.load_profile("nonexistent")

    def test_cache_works(self) -> None:
        """Test that profile caching works."""
        loader = ProfileLoader()

        # Load first time
        profile1, _ = loader.load_profile("python")

        # Load second time (should be from cache)
        profile2, _ = loader.load_profile("python")

        # Should be same object (from cache)
        assert profile1 is profile2

    def test_clear_cache(self) -> None:
        """Test clearing profile cache."""
        loader = ProfileLoader()

        # Load and cache
        profile1, _ = loader.load_profile("python")
        assert "python" in loader._cache

        # Clear cache
        loader.clear_cache()
        assert "python" not in loader._cache

    def test_load_custom_profile(self, tmp_path: Path) -> None:
        """Test loading custom profile from file."""
        # Create custom profile directory
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        # Create custom profile file
        profile_file = profiles_dir / "custom.yml"
        profile_file.write_text("""
name: custom
description: Custom test profile
versions:
  - "1.0"
  - "2.0"
default_version: "1.0"
system_dependencies:
  - curl
docker_layers:
  - "RUN echo test"
""")

        # Load custom profile
        loader = ProfileLoader(profiles_dir)
        profile, version = loader.load_profile("custom")

        assert profile.name == "custom"
        assert profile.description == "Custom test profile"
        assert version == "1.0"
        assert "curl" in profile.system_dependencies

    def test_load_custom_profile_with_version(self, tmp_path: Path) -> None:
        """Test loading custom profile with specific version."""
        # Create custom profile directory
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        # Create custom profile file
        profile_file = profiles_dir / "custom.yml"
        profile_file.write_text("""
name: custom
description: Custom test profile
versions:
  - "1.0"
  - "2.0"
default_version: "1.0"
""")

        # Load with version 2.0
        loader = ProfileLoader(profiles_dir)
        profile, version = loader.load_profile("custom:2.0")

        assert profile.name == "custom"
        assert version == "2.0"

    def test_load_invalid_yaml(self, tmp_path: Path) -> None:
        """Test loading profile with invalid YAML."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        profile_file = profiles_dir / "invalid.yml"
        profile_file.write_text("{ invalid yaml [")

        loader = ProfileLoader(profiles_dir)

        with pytest.raises(InvalidProfileError, match="Failed to parse YAML"):
            loader.load_profile("invalid")

    def test_load_profile_missing_required_fields(self, tmp_path: Path) -> None:
        """Test loading profile missing required fields."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        profile_file = profiles_dir / "incomplete.yml"
        profile_file.write_text("""
name: incomplete
description: Missing required fields
""")

        loader = ProfileLoader(profiles_dir)

        with pytest.raises(InvalidProfileError, match="Invalid profile definition"):
            loader.load_profile("incomplete")
