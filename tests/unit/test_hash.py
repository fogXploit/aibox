"""Unit tests for project hash utilities."""

from pathlib import Path

from aibox.utils.hash import generate_project_hash, get_project_name


class TestGenerateProjectHash:
    """Tests for generate_project_hash function."""

    def test_hash_is_deterministic(self, tmp_path: Path) -> None:
        """Test that same path always produces same hash."""
        hash1 = generate_project_hash(tmp_path)
        hash2 = generate_project_hash(tmp_path)
        assert hash1 == hash2

    def test_hash_length(self, tmp_path: Path) -> None:
        """Test that hash is 8 characters."""
        hash_str = generate_project_hash(tmp_path)
        assert len(hash_str) == 8

    def test_hash_is_hex(self, tmp_path: Path) -> None:
        """Test that hash contains only hex characters."""
        hash_str = generate_project_hash(tmp_path)
        assert all(c in "0123456789abcdef" for c in hash_str)

    def test_different_paths_different_hashes(self, tmp_path: Path) -> None:
        """Test that different paths produce different hashes."""
        dir1 = tmp_path / "project1"
        dir2 = tmp_path / "project2"
        dir1.mkdir()
        dir2.mkdir()

        hash1 = generate_project_hash(dir1)
        hash2 = generate_project_hash(dir2)
        assert hash1 != hash2

    def test_hash_works_with_string_path(self, tmp_path: Path) -> None:
        """Test that hash works with string path."""
        hash_str = generate_project_hash(str(tmp_path))
        assert len(hash_str) == 8

    def test_hash_resolves_relative_paths(self) -> None:
        """Test that relative paths are resolved to absolute."""
        # Same directory should produce same hash regardless of how it's referenced
        hash1 = generate_project_hash(".")
        hash2 = generate_project_hash(Path.cwd())
        assert hash1 == hash2


class TestGetProjectName:
    """Tests for get_project_name function."""

    def test_get_name_from_path(self, tmp_path: Path) -> None:
        """Test extracting project name from path."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        assert get_project_name(project_dir) == "my-project"

    def test_get_name_from_string(self, tmp_path: Path) -> None:
        """Test extracting project name from string path."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        assert get_project_name(str(project_dir)) == "test-project"

    def test_get_name_handles_trailing_slash(self, tmp_path: Path) -> None:
        """Test that trailing slash doesn't affect name."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        name1 = get_project_name(str(project_dir))
        name2 = get_project_name(str(project_dir) + "/")
        assert name1 == name2 == "project"

    def test_get_name_resolves_relative_path(self) -> None:
        """Test that relative paths are resolved."""
        name = get_project_name(".")
        assert name == Path.cwd().name
