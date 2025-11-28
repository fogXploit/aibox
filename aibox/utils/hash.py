"""
Project hash generation utilities.

Generate unique, deterministic hashes for project directories to isolate
project state and avoid naming conflicts.
"""

import hashlib
from pathlib import Path


def generate_project_hash(project_dir: str | Path) -> str:
    """
    Generate a unique hash for a project directory.

    The hash is deterministic (same directory always produces same hash)
    and is used to isolate project state in ~/.aibox/projects/<hash>/.

    Args:
        project_dir: Path to project directory

    Returns:
        8-character hex hash string

    Example:
        >>> generate_project_hash("/home/user/my-project")
        'a1b2c3d4'
    """
    # Convert to Path and resolve to absolute path
    abs_path = Path(project_dir).resolve()

    # Use SHA256 for good distribution, take first 8 chars
    hash_obj = hashlib.sha256(str(abs_path).encode("utf-8"))
    return hash_obj.hexdigest()[:8]


def get_project_name(project_dir: str | Path) -> str:
    """
    Get the project name from directory path.

    Args:
        project_dir: Path to project directory

    Returns:
        Directory name (last component of path)

    Example:
        >>> get_project_name("/home/user/my-project")
        'my-project'
    """
    return Path(project_dir).resolve().name


def get_project_storage_dir(project_dir: str | Path) -> str:
    """
    Generate a human-readable storage directory name for a project.

    Combines the project name with a short hash for uniqueness while
    maintaining readability. Format: <name>-<hash>

    Args:
        project_dir: Path to project directory

    Returns:
        Storage directory name (name-hash format)

    Example:
        >>> get_project_storage_dir("/home/user/my-project")
        'my-project-a1b2c3d4'
    """
    name = get_project_name(project_dir)
    hash_val = generate_project_hash(project_dir)
    return f"{name}-{hash_val}"
