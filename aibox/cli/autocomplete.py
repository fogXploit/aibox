"""
Autocompletion functions for aibox CLI.

Provides custom autocompletion for dynamic values like profiles, providers, and slots.
These functions are called by Typer when users press TAB in their shell.
"""

from pathlib import Path

from aibox.containers.slot import SlotManager
from aibox.profiles.loader import ProfileLoader
from aibox.providers.registry import ProviderRegistry
from aibox.utils.hash import get_project_storage_dir


def complete_profile_name() -> list[str]:
    """
    Autocomplete profile names with versions.

    Returns:
        List of profile specifications (e.g., ["python", "python:3.11", "nodejs:20"])
    """
    try:
        loader = ProfileLoader()
        all_profiles = loader.list_profiles()

        completions = []
        for profile_name in all_profiles:
            # Add base profile name
            completions.append(profile_name)

            # Add profile:version variants
            try:
                profile, _ = loader.load_profile(profile_name)
                if profile.versions:
                    for version in profile.versions:
                        completions.append(f"{profile_name}:{version}")
            except Exception:
                # If we can't load profile details, just skip versions
                pass

        return sorted(completions)
    except Exception:
        # Fail gracefully if autocomplete fails
        return []


def complete_provider_name() -> list[str]:
    """
    Autocomplete AI provider names.

    Returns:
        List of provider names (e.g., ["claude", "gemini", "openai"])
    """
    try:
        return ProviderRegistry.list_providers()
    except Exception:
        # Fail gracefully if autocomplete fails
        return []


def complete_slot_number() -> list[str]:
    """
    Autocomplete configured slot numbers for current project.

    Returns:
        List of configured slot numbers as strings (e.g., ["1", "2", "3"])
    """
    try:
        project_root = Path.cwd()
        storage_dir = get_project_storage_dir(project_root)
        slot_manager = SlotManager(storage_dir)
        slots = slot_manager.list_slots()

        # Return slot numbers as strings (Typer expects strings)
        return [str(slot["slot"]) for slot in slots]
    except Exception:
        # Fail gracefully if autocomplete fails
        # Return all possible slots if we can't determine configured ones
        return [str(i) for i in range(1, 11)]
