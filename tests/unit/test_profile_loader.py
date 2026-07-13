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
        assert "flutter" in profiles
        assert "java" in profiles
        assert "dotnet" in profiles
        assert "php" in profiles
        assert "ruby" in profiles
        assert "cpp" in profiles

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
            assert "versions_list" in profile
            assert "default_version" in profile

            # versions is a display string, versions_list is the raw list
            versions_list = profile["versions_list"]
            assert isinstance(versions_list, list)
            assert profile["versions"] == ", ".join(versions_list)
            assert profile["default_version"] in versions_list

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

    def test_load_builtin_nodejs_profile(self) -> None:
        """Test that the nodejs profile offers current versions and has no npm upgrade layer."""
        loader = ProfileLoader()
        profile, version = loader.load_profile("nodejs")

        assert profile.name == "nodejs"
        assert profile.versions == ["20", "22", "24"]
        assert profile.default_version == "24"
        assert version == "24"
        # NodeSource packages bundle a current npm; upgrading breaks on older Node
        assert not any("npm install -g npm@latest" in layer for layer in profile.docker_layers)

    def test_load_builtin_go_profile(self) -> None:
        """Test that the go profile offers current versions with the official tarball."""
        loader = ProfileLoader()
        profile, version = loader.load_profile("go")

        assert profile.name == "go"
        assert profile.versions == ["1.24.13", "1.25.12", "1.26.5"]
        assert profile.default_version == "1.25.12"
        assert version == "1.25.12"
        assert any("go.dev/dl/go" in layer for layer in profile.docker_layers)

    def test_load_builtin_rust_profile(self) -> None:
        """Test that the rust profile offers current pins alongside channels."""
        loader = ProfileLoader()
        profile, version = loader.load_profile("rust")

        assert profile.name == "rust"
        assert profile.versions == ["stable", "beta", "nightly", "1.95.0", "1.96.1", "1.97.0"]
        assert profile.default_version == "stable"
        assert version == "stable"
        assert any("rustup" in layer for layer in profile.docker_layers)

    def test_load_builtin_flutter_profile(self) -> None:
        """Test that the flutter profile offers current stable versions."""
        loader = ProfileLoader()
        profile, version = loader.load_profile("flutter")

        assert profile.name == "flutter"
        assert profile.versions == ["3.44.3", "3.44.6"]
        assert profile.default_version == "3.44.6"
        assert version == "3.44.6"
        assert any(
            "storage.googleapis.com/flutter_infra_release" in layer
            for layer in profile.docker_layers
        )

    def test_load_builtin_java_profile(self) -> None:
        """Test that the java profile installs Eclipse Temurin LTS JDKs via Adoptium."""
        loader = ProfileLoader()
        profile, version = loader.load_profile("java")

        assert profile.name == "java"
        assert profile.versions == ["17", "21", "25"]
        assert profile.default_version == "21"
        assert version == "21"
        assert "wget" in profile.system_dependencies
        assert "gpg" in profile.system_dependencies
        assert "ca-certificates" in profile.system_dependencies
        assert "apt-transport-https" in profile.system_dependencies
        assert any("packages.adoptium.net" in layer for layer in profile.docker_layers)
        assert any("temurin-${VERSION}-jdk" in layer for layer in profile.docker_layers)
        assert "java -version" in profile.post_install
        assert "javac -version" in profile.post_install

    def test_load_builtin_dotnet_profile(self) -> None:
        """Test that the dotnet profile installs the SDK from the Microsoft apt repo."""
        loader = ProfileLoader()
        profile, version = loader.load_profile("dotnet")

        assert profile.name == "dotnet"
        assert profile.versions == ["8.0", "9.0", "10.0"]
        assert profile.default_version == "10.0"
        assert version == "10.0"
        assert "wget" in profile.system_dependencies
        assert "ca-certificates" in profile.system_dependencies
        assert any("packages-microsoft-prod.deb" in layer for layer in profile.docker_layers)
        assert any("dotnet-sdk-${VERSION}" in layer for layer in profile.docker_layers)
        assert profile.env_vars.get("DOTNET_CLI_TELEMETRY_OPTOUT") == "1"
        assert profile.env_vars.get("DOTNET_NOLOGO") == "1"
        assert "dotnet --version" in profile.post_install

    def test_load_builtin_php_profile(self) -> None:
        """Test that the php profile installs PHP from the Sury repo plus Composer."""
        loader = ProfileLoader()
        profile, version = loader.load_profile("php")

        assert profile.name == "php"
        assert profile.versions == ["8.2", "8.3", "8.4", "8.5"]
        assert profile.default_version == "8.4"
        assert version == "8.4"
        assert "curl" in profile.system_dependencies
        assert "ca-certificates" in profile.system_dependencies
        assert "apt-transport-https" in profile.system_dependencies
        assert any("packages.sury.org/php" in layer for layer in profile.docker_layers)
        assert any("php${VERSION}-cli" in layer for layer in profile.docker_layers)
        assert any("getcomposer.org" in layer for layer in profile.docker_layers)
        assert "php --version" in profile.post_install
        assert "composer --version" in profile.post_install

    def test_load_builtin_ruby_profile(self) -> None:
        """Test that the ruby profile compiles current Ruby releases from source."""
        loader = ProfileLoader()
        profile, version = loader.load_profile("ruby")

        assert profile.name == "ruby"
        assert profile.versions == ["3.3.11", "3.4.10", "4.0.5"]
        assert profile.default_version == "3.4.10"
        assert version == "3.4.10"
        # Build deps; libyaml-dev and libssl-dev failures only surface late in the build
        assert "build-essential" in profile.system_dependencies
        assert "libssl-dev" in profile.system_dependencies
        assert "libyaml-dev" in profile.system_dependencies
        assert any("cache.ruby-lang.org" in layer for layer in profile.docker_layers)
        # major.minor is derived with shell (plain ${VERSION%.*} is not substituted)
        assert any("cut -d. -f1-2" in layer for layer in profile.docker_layers)
        assert "ruby --version" in profile.post_install
        assert "gem --version" in profile.post_install

    def test_load_builtin_cpp_profile(self) -> None:
        """Test that the cpp profile uses only the Debian system toolchain."""
        loader = ProfileLoader()
        profile, version = loader.load_profile("cpp")

        assert profile.name == "cpp"
        assert profile.versions == ["system"]
        assert profile.default_version == "system"
        assert version == "system"
        assert "build-essential" in profile.system_dependencies
        assert "gdb" in profile.system_dependencies
        assert "cmake" in profile.system_dependencies
        assert "pkg-config" in profile.system_dependencies
        assert "make" in profile.system_dependencies
        assert profile.docker_layers == []
        assert "gcc --version" in profile.post_install
        assert "g++ --version" in profile.post_install

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

    def test_builtin_profiles_valid_docker_layers(self) -> None:
        """Test that built-in profiles have valid docker layers (no quoted commands)."""
        loader = ProfileLoader()
        profiles = loader.list_profiles()
        for name in profiles:
            profile, _ = loader.load_profile(name)
            for layer in profile.docker_layers:
                # Quoted commands like RUN '...' or RUN "..." fail during docker build
                assert not layer.startswith("RUN '"), (
                    f"Profile '{name}' has a layer starting with RUN ': {layer}"
                )
                assert not layer.startswith('RUN "'), (
                    f"Profile '{name}' has a layer starting with RUN \": {layer}"
                )
