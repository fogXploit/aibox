"""
Unit tests for aibox error classes.

Tests cover:
- Error hierarchy and inheritance
- Error message formatting
- Suggestion and documentation link handling
- Provider-specific error types
"""

from aibox.utils.errors import (
    AiboxError,
    APIKeyNotFoundError,
    ConfigError,
    ConfigNotFoundError,
    ContainerStartError,
    DockerError,
    DockerNotFoundError,
    ImageBuildError,
    InvalidConfigError,
    InvalidProfileError,
    NoAvailableSlotsError,
    ProfileError,
    ProfileNotFoundError,
    ProviderError,
    ProviderInstallError,
    ProviderNotFoundError,
    SlotError,
    SlotNotFoundError,
)


class TestAiboxError:
    """Tests for base AiboxError class."""

    def test_simple_message(self) -> None:
        """Test error with just a message."""
        error = AiboxError("Something went wrong")
        assert error.message == "Something went wrong"
        assert error.suggestion is None
        assert error.doc_link is None
        assert str(error) == "Something went wrong"

    def test_message_with_suggestion(self) -> None:
        """Test error with message and suggestion."""
        error = AiboxError("Something went wrong", suggestion="Try running with --verbose")
        assert error.message == "Something went wrong"
        assert error.suggestion == "Try running with --verbose"
        assert "Suggestion: Try running with --verbose" in str(error)

    def test_message_with_doc_link(self) -> None:
        """Test error with message and documentation link."""
        error = AiboxError("Something went wrong", doc_link="https://docs.example.com")
        assert error.message == "Something went wrong"
        assert error.doc_link == "https://docs.example.com"
        assert "See: https://docs.example.com" in str(error)

    def test_full_error(self) -> None:
        """Test error with all fields populated."""
        error = AiboxError(
            "Something went wrong",
            suggestion="Try running with --verbose",
            doc_link="https://docs.example.com",
        )
        error_str = str(error)
        assert "Something went wrong" in error_str
        assert "Suggestion: Try running with --verbose" in error_str
        assert "See: https://docs.example.com" in error_str


class TestConfigErrors:
    """Tests for configuration error classes."""

    def test_config_error_inheritance(self) -> None:
        """Test ConfigError inherits from AiboxError."""
        error = ConfigError("Config error")
        assert isinstance(error, AiboxError)
        assert isinstance(error, ConfigError)

    def test_invalid_config_error(self) -> None:
        """Test InvalidConfigError with helpful message."""
        error = InvalidConfigError(
            "Invalid profile format",
            suggestion="Check your .aibox/config.yml syntax",
        )
        assert isinstance(error, ConfigError)
        assert "Invalid profile format" in str(error)
        assert "Check your .aibox/config.yml syntax" in str(error)

    def test_config_not_found_error(self) -> None:
        """Test ConfigNotFoundError with helpful message."""
        error = ConfigNotFoundError(
            "Configuration file not found",
            suggestion="Run 'aibox init' to create default configuration",
        )
        assert isinstance(error, ConfigError)
        assert "Configuration file not found" in str(error)
        assert "Run 'aibox init' to create default configuration" in str(error)


class TestDockerErrors:
    """Tests for Docker error classes."""

    def test_docker_error_inheritance(self) -> None:
        """Test DockerError inherits from AiboxError."""
        error = DockerError("Docker error")
        assert isinstance(error, AiboxError)
        assert isinstance(error, DockerError)

    def test_docker_not_found_error(self) -> None:
        """Test DockerNotFoundError with helpful message."""
        error = DockerNotFoundError(
            "Docker is not installed or not running",
            suggestion="Install Docker Desktop or start the Docker daemon",
        )
        assert isinstance(error, DockerError)
        assert "Docker is not installed or not running" in str(error)
        assert "Install Docker Desktop or start the Docker daemon" in str(error)

    def test_image_build_error(self) -> None:
        """Test ImageBuildError with helpful message."""
        error = ImageBuildError(
            "Failed to build Docker image",
            suggestion="Check your profile definitions and Docker logs",
        )
        assert isinstance(error, DockerError)
        assert "Failed to build Docker image" in str(error)
        assert "Check your profile definitions and Docker logs" in str(error)

    def test_container_start_error(self) -> None:
        """Test ContainerStartError with helpful message."""
        error = ContainerStartError(
            "Container failed to start",
            suggestion="Check if the port is already in use or if Docker has enough resources",
        )
        assert isinstance(error, DockerError)
        assert "Container failed to start" in str(error)
        assert "Check if the port is already in use" in str(error)


class TestProfileErrors:
    """Tests for profile error classes."""

    def test_profile_error_inheritance(self) -> None:
        """Test ProfileError inherits from AiboxError."""
        error = ProfileError("Profile error")
        assert isinstance(error, AiboxError)
        assert isinstance(error, ProfileError)

    def test_profile_not_found_error(self) -> None:
        """Test ProfileNotFoundError with helpful message."""
        error = ProfileNotFoundError(
            "Profile 'python:3.14' not found",
            suggestion="Run 'aibox profile list' to see available profiles",
        )
        assert isinstance(error, ProfileError)
        assert "Profile 'python:3.14' not found" in str(error)
        assert "Run 'aibox profile list' to see available profiles" in str(error)

    def test_invalid_profile_error(self) -> None:
        """Test InvalidProfileError with helpful message."""
        error = InvalidProfileError(
            "Profile definition is missing required field 'name'",
            suggestion="Check the YAML syntax in your profile definition",
        )
        assert isinstance(error, ProfileError)
        assert "Profile definition is missing required field 'name'" in str(error)
        assert "Check the YAML syntax in your profile definition" in str(error)


class TestProviderErrors:
    """Tests for AI provider error classes."""

    def test_provider_error_inheritance(self) -> None:
        """Test ProviderError inherits from AiboxError."""
        error = ProviderError("Provider error")
        assert isinstance(error, AiboxError)
        assert isinstance(error, ProviderError)

    def test_provider_not_found_error(self) -> None:
        """Test ProviderNotFoundError with helpful message."""
        error = ProviderNotFoundError(
            "AI provider 'unknown' not found",
            suggestion="Available providers: claude, gemini, openai",
        )
        assert isinstance(error, ProviderError)
        assert "AI provider 'unknown' not found" in str(error)
        assert "Available providers: claude, gemini, openai" in str(error)

    def test_api_key_not_found_error(self) -> None:
        """Test APIKeyNotFoundError with helpful message."""
        error = APIKeyNotFoundError(
            "ANTHROPIC_API_KEY not found in environment",
            suggestion="Set your API key: export ANTHROPIC_API_KEY=your-key-here",
        )
        assert isinstance(error, ProviderError)
        assert "ANTHROPIC_API_KEY not found in environment" in str(error)
        assert "Set your API key: export ANTHROPIC_API_KEY=your-key-here" in str(error)

    def test_provider_install_error(self) -> None:
        """Test ProviderInstallError with helpful message."""
        error = ProviderInstallError(
            "Failed to install Claude CLI",
            suggestion="Check your internet connection and try again",
        )
        assert isinstance(error, ProviderError)
        assert "Failed to install Claude CLI" in str(error)
        assert "Check your internet connection and try again" in str(error)


class TestSlotErrors:
    """Tests for slot error classes."""

    def test_slot_error_inheritance(self) -> None:
        """Test SlotError inherits from AiboxError."""
        error = SlotError("Slot error")
        assert isinstance(error, AiboxError)
        assert isinstance(error, SlotError)

    def test_no_available_slots_error(self) -> None:
        """Test NoAvailableSlotsError with helpful message."""
        error = NoAvailableSlotsError(
            "All 10 slots are currently in use",
            suggestion="Stop an existing container or wait for one to finish",
        )
        assert isinstance(error, SlotError)
        assert "All 10 slots are currently in use" in str(error)
        assert "Stop an existing container or wait for one to finish" in str(error)

    def test_slot_not_found_error(self) -> None:
        """Test SlotNotFoundError with helpful message."""
        error = SlotNotFoundError(
            "Slot 5 does not exist",
            suggestion="Run 'aibox slot list' to see active slots",
        )
        assert isinstance(error, SlotError)
        assert "Slot 5 does not exist" in str(error)
        assert "Run 'aibox slot list' to see active slots" in str(error)
