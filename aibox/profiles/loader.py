"""
Profile loader for reading YAML profile definitions.

Loads profile definitions from YAML files in aibox/profiles/definitions/
and provides caching for performance.
"""

from pathlib import Path

import yaml
from pydantic import ValidationError

from aibox.profiles.models import ProfileDefinition
from aibox.utils.errors import InvalidProfileError, ProfileNotFoundError


class ProfileLoader:
    """Loads and caches profile definitions from YAML files."""

    def __init__(self, profiles_dir: Path | None = None) -> None:
        """
        Initialize profile loader.

        Args:
            profiles_dir: Directory containing profile YAML files
                         (defaults to aibox/profiles/definitions/)
        """
        if profiles_dir is None:
            # Default to definitions directory next to this file
            self.profiles_dir = Path(__file__).parent / "definitions"
        else:
            self.profiles_dir = Path(profiles_dir)

        self._cache: dict[str, ProfileDefinition] = {}

    def load_profile(self, profile_spec: str) -> tuple[ProfileDefinition, str]:
        """
        Load profile by spec (name or name:version).

        Args:
            profile_spec: Profile specification like "python" or "python:3.12"

        Returns:
            Tuple of (ProfileDefinition, version_to_use)

        Raises:
            ProfileNotFoundError: If profile doesn't exist
            InvalidProfileError: If profile YAML is invalid or version unavailable
        """
        name, requested_version = self._parse_spec(profile_spec)

        # Load profile definition (from cache or file)
        profile = self._load_profile_definition(name)

        # Determine version to use
        try:
            version = profile.get_version(requested_version)
        except ValueError as e:
            raise InvalidProfileError(
                message=str(e), suggestion=f"Use one of: {', '.join(profile.versions)}"
            ) from e

        return profile, version

    def list_profiles(self) -> list[str]:
        """
        List all available profiles.

        Returns:
            List of profile names (without .yml extension)
        """
        if not self.profiles_dir.exists():
            return []

        profiles = []
        for profile_file in sorted(self.profiles_dir.glob("*.yml")):
            profiles.append(profile_file.stem)

        return profiles

    def list_profiles_with_info(self) -> list[dict[str, str]]:
        """
        List profiles with their descriptions and versions.

        Returns:
            List of dicts with name, description, and versions
        """
        profiles = []
        for name in self.list_profiles():
            try:
                profile = self._load_profile_definition(name)
                profiles.append(
                    {
                        "name": profile.name,
                        "description": profile.description,
                        "versions": ", ".join(profile.versions),
                        "default_version": profile.default_version,
                    }
                )
            except (ProfileNotFoundError, InvalidProfileError):
                # Skip invalid profiles
                continue

        return profiles

    def _load_profile_definition(self, name: str) -> ProfileDefinition:
        """
        Load profile definition from file or cache.

        Args:
            name: Profile name

        Returns:
            ProfileDefinition instance

        Raises:
            ProfileNotFoundError: If profile file doesn't exist
            InvalidProfileError: If YAML is invalid or validation fails
        """
        # Check cache first
        if name in self._cache:
            return self._cache[name]

        # Find profile file
        profile_file = self.profiles_dir / f"{name}.yml"
        if not profile_file.exists():
            raise ProfileNotFoundError(
                message=f"Profile '{name}' not found",
                suggestion=f"Available profiles: {', '.join(self.list_profiles())}",
            )

        # Load and parse YAML
        try:
            with open(profile_file) as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict):
                raise InvalidProfileError(
                    message=f"Invalid profile file {profile_file}: expected YAML dictionary",
                    suggestion="Check profile YAML structure",
                )

        except yaml.YAMLError as e:
            raise InvalidProfileError(
                message=f"Failed to parse YAML in {profile_file}: {e}",
                suggestion="Check YAML syntax",
            ) from e
        except OSError as e:
            raise InvalidProfileError(
                message=f"Failed to read profile file {profile_file}: {e}",
                suggestion="Check file permissions",
            ) from e

        # Validate with Pydantic
        try:
            profile = ProfileDefinition(**data)
        except ValidationError as e:
            raise InvalidProfileError(
                message=f"Invalid profile definition for '{name}'",
                suggestion=f"Fix validation errors:\n{e}",
            ) from e

        # Cache and return
        self._cache[name] = profile
        return profile

    def _parse_spec(self, spec: str) -> tuple[str, str | None]:
        """
        Parse profile spec into name and version.

        Args:
            spec: Profile spec like "python" or "python:3.12"

        Returns:
            Tuple of (name, version) where version may be None

        Examples:
            >>> _parse_spec("python")
            ("python", None)
            >>> _parse_spec("python:3.12")
            ("python", "3.12")
            >>> _parse_spec("nodejs:20")
            ("nodejs", "20")
        """
        parts = spec.split(":", 1)
        name = parts[0].strip()

        if not name:
            raise InvalidProfileError(
                message="Profile spec cannot be empty",
                suggestion="Use format like 'python' or 'python:3.12'",
            )

        version = parts[1].strip() if len(parts) > 1 else None

        return name, version

    def clear_cache(self) -> None:
        """Clear the profile cache."""
        self._cache.clear()
