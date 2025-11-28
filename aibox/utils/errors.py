"""
Custom exception classes for aibox.

All aibox exceptions inherit from AiboxError and include:
- Clear error messages describing the problem
- Actionable suggestions for resolution
- Optional documentation links
"""


class AiboxError(Exception):
    """Base exception class for all aibox errors."""

    def __init__(
        self, message: str, suggestion: str | None = None, doc_link: str | None = None
    ) -> None:
        """
        Initialize an aibox error.

        Args:
            message: Clear description of what went wrong
            suggestion: Actionable suggestion for how to fix the issue
            doc_link: Optional URL to relevant documentation
        """
        self.message = message
        self.suggestion = suggestion
        self.doc_link = doc_link

        full_message = message
        if suggestion:
            full_message += f"\n\nSuggestion: {suggestion}"
        if doc_link:
            full_message += f"\n\nSee: {doc_link}"

        super().__init__(full_message)


# Configuration Errors


class ConfigError(AiboxError):
    """Base exception for configuration-related errors."""


class InvalidConfigError(ConfigError):
    """Raised when configuration is invalid or fails validation."""


class ConfigNotFoundError(ConfigError):
    """Raised when a required configuration file is not found."""


# Docker Errors


class DockerError(AiboxError):
    """Base exception for Docker-related errors."""


class DockerNotFoundError(DockerError):
    """Raised when Docker is not installed or not accessible."""


class ImageBuildError(DockerError):
    """Raised when Docker image build fails."""


class ContainerStartError(DockerError):
    """Raised when container fails to start."""


# Profile Errors


class ProfileError(AiboxError):
    """Base exception for profile-related errors."""


class ProfileNotFoundError(ProfileError):
    """Raised when a requested profile is not found."""


class InvalidProfileError(ProfileError):
    """Raised when a profile definition is invalid."""


# Provider Errors


class ProviderError(AiboxError):
    """Base exception for AI provider-related errors."""


class ProviderNotFoundError(ProviderError):
    """Raised when a requested AI provider is not found."""


class APIKeyNotFoundError(ProviderError):
    """Raised when required API key is not found in environment."""


class ProviderInstallError(ProviderError):
    """Raised when AI provider installation fails."""


# Slot Errors


class SlotError(AiboxError):
    """Base exception for slot-related errors."""


class NoAvailableSlotsError(SlotError):
    """Raised when all slots are in use."""


class SlotNotFoundError(SlotError):
    """Raised when specified slot does not exist."""
