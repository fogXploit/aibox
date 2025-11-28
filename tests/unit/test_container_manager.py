"""Unit tests for container manager."""

from unittest.mock import Mock, patch

import pytest
from docker.errors import APIError, ImageNotFound, NotFound

from aibox.containers.manager import ContainerManager
from aibox.utils.errors import (
    ContainerStartError,
    DockerError,
    DockerNotFoundError,
    ImageBuildError,
)


class TestContainerManagerInit:
    """Tests for ContainerManager initialization."""

    @patch("aibox.containers.manager.docker.from_env")
    def test_init_success(self, mock_from_env: Mock) -> None:
        """Test successful initialization."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        assert manager.client == mock_client
        mock_client.ping.assert_called_once()

    @patch("aibox.containers.manager.docker.from_env")
    def test_init_docker_not_running(self, mock_from_env: Mock) -> None:
        """Test initialization when Docker is not running."""
        from docker.errors import DockerException

        mock_from_env.side_effect = DockerException("Docker not available")

        with pytest.raises(DockerNotFoundError):
            ContainerManager()


class TestContainerManagerBuild:
    """Tests for image building."""

    @patch("aibox.containers.manager.docker.from_env")
    def test_build_image_success(self, mock_from_env: Mock) -> None:
        """Test successful image build."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        # Make build return an iterable of log chunks
        mock_client.api.build.return_value = [
            {"stream": "Step 1/3 : FROM debian:bookworm-slim\n"},
            {"stream": "Step 2/3 : RUN apt-get update\n"},
            {"stream": "Successfully built abc123\n"},
        ]
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        manager.build_image(
            dockerfile_path="/path/to/dockerfile", tag="test:latest", buildargs={"VERSION": "1.0"}
        )

        mock_client.api.build.assert_called_once_with(
            path="/path/to/dockerfile",
            tag="test:latest",
            buildargs={"VERSION": "1.0"},
            rm=True,
            pull=False,
            nocache=False,
            cache_from=[],
            decode=True,
        )

    @patch("aibox.containers.manager.docker.from_env")
    def test_build_image_failure(self, mock_from_env: Mock) -> None:
        """Test image build failure."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        # Make build return an iterable with an error chunk
        mock_client.api.build.return_value = [
            {"stream": "Step 1/3 : FROM debian:bookworm-slim\n"},
            {"error": "Build failed: syntax error"},
        ]
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        # Provide a progress_callback to trigger error handling
        progress_callback = Mock()
        with pytest.raises(ImageBuildError):
            manager.build_image("/path", "test:latest", progress_callback=progress_callback)


class TestContainerManagerCreate:
    """Tests for container creation."""

    @patch("aibox.containers.manager.docker.from_env")
    def test_create_container_success(self, mock_from_env: Mock) -> None:
        """Test successful container creation."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_container = Mock()
        mock_client.containers.create.return_value = mock_container
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        volumes = {"/host": {"bind": "/container", "mode": "rw"}}
        env = {"KEY": "value"}

        container = manager.create_container(
            image="test:latest", name="test-container", volumes=volumes, environment=env
        )

        assert container == mock_container
        mock_client.containers.create.assert_called_once_with(
            image="test:latest",
            name="test-container",
            volumes=volumes,
            environment=env,
            command=None,
            working_dir="/workspace",
            ports={},
            network_mode=None,
            auto_remove=True,
            detach=True,
            stdin_open=True,
            tty=True,
        )

    @patch("aibox.containers.manager.docker.from_env")
    def test_create_container_image_not_found(self, mock_from_env: Mock) -> None:
        """Test container creation with missing image."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.create.side_effect = ImageNotFound("Image not found")
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        with pytest.raises(ContainerStartError):
            manager.create_container("missing:latest", "test", {})

    @patch("aibox.containers.manager.docker.from_env")
    def test_create_container_api_error(self, mock_from_env: Mock) -> None:
        """Test container creation with API error."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.create.side_effect = APIError("API error")
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        with pytest.raises(ContainerStartError):
            manager.create_container("test:latest", "test", {})


class TestContainerManagerStart:
    """Tests for starting containers."""

    @patch("aibox.containers.manager.docker.from_env")
    def test_start_container_success(self, mock_from_env: Mock) -> None:
        """Test successful container start."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_from_env.return_value = mock_client

        mock_container = Mock()

        manager = ContainerManager()
        manager.start_container(mock_container)

        mock_container.start.assert_called_once()

    @patch("aibox.containers.manager.docker.from_env")
    def test_start_container_failure(self, mock_from_env: Mock) -> None:
        """Test container start failure."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_from_env.return_value = mock_client

        mock_container = Mock()
        mock_container.start.side_effect = APIError("Start failed")
        mock_container.name = "test-container"

        manager = ContainerManager()
        with pytest.raises(ContainerStartError):
            manager.start_container(mock_container)


class TestContainerManagerGet:
    """Tests for getting containers."""

    @patch("aibox.containers.manager.docker.from_env")
    def test_get_container_exists(self, mock_from_env: Mock) -> None:
        """Test getting existing container."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_container = Mock()
        mock_client.containers.get.return_value = mock_container
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        container = manager.get_container("test-container")

        assert container == mock_container
        mock_client.containers.get.assert_called_once_with("test-container")

    @patch("aibox.containers.manager.docker.from_env")
    def test_get_container_not_found(self, mock_from_env: Mock) -> None:
        """Test getting non-existent container."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.get.side_effect = NotFound("Container not found")
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        container = manager.get_container("missing")

        assert container is None

    @patch("aibox.containers.manager.docker.from_env")
    def test_get_container_api_error(self, mock_from_env: Mock) -> None:
        """Test getting container with API error."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.get.side_effect = APIError("API error")
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        container = manager.get_container("test")

        assert container is None


class TestContainerManagerList:
    """Tests for listing containers."""

    @patch("aibox.containers.manager.docker.from_env")
    def test_list_containers(self, mock_from_env: Mock) -> None:
        """Test listing containers."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_containers = [Mock(), Mock()]
        mock_client.containers.list.return_value = mock_containers
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        containers = manager.list_containers()

        assert containers == mock_containers
        mock_client.containers.list.assert_called_once_with(all=True, filters=None)

    @patch("aibox.containers.manager.docker.from_env")
    def test_list_containers_with_filters(self, mock_from_env: Mock) -> None:
        """Test listing containers with filters."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.list.return_value = []
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        filters = {"name": "aibox-"}
        manager.list_containers(filters=filters)

        mock_client.containers.list.assert_called_once_with(all=True, filters=filters)

    @patch("aibox.containers.manager.docker.from_env")
    def test_list_containers_api_error(self, mock_from_env: Mock) -> None:
        """Test listing containers with API error."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.list.side_effect = APIError("API error")
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        containers = manager.list_containers()

        assert containers == []


class TestContainerManagerStop:
    """Tests for stopping containers."""

    @patch("aibox.containers.manager.docker.from_env")
    def test_stop_container_success(self, mock_from_env: Mock) -> None:
        """Test successful container stop."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_container = Mock()
        mock_client.containers.get.return_value = mock_container
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        manager.stop_container("test-container", timeout=5)

        mock_client.containers.get.assert_called_once_with("test-container")
        mock_container.stop.assert_called_once_with(timeout=5)

    @patch("aibox.containers.manager.docker.from_env")
    def test_stop_container_not_found(self, mock_from_env: Mock) -> None:
        """Test stopping non-existent container."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.get.side_effect = NotFound("Container not found")
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        with pytest.raises(DockerError):
            manager.stop_container("missing")

    @patch("aibox.containers.manager.docker.from_env")
    def test_stop_container_api_error(self, mock_from_env: Mock) -> None:
        """Test stopping container with API error."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_container = Mock()
        mock_container.stop.side_effect = APIError("Stop failed")
        mock_client.containers.get.return_value = mock_container
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        with pytest.raises(DockerError):
            manager.stop_container("test")


class TestContainerManagerRemove:
    """Tests for removing containers."""

    @patch("aibox.containers.manager.docker.from_env")
    def test_remove_container_success(self, mock_from_env: Mock) -> None:
        """Test successful container removal."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_container = Mock()
        mock_client.containers.get.return_value = mock_container
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        manager.remove_container("test-container", force=True)

        mock_container.remove.assert_called_once_with(force=True)

    @patch("aibox.containers.manager.docker.from_env")
    def test_remove_container_not_found(self, mock_from_env: Mock) -> None:
        """Test removing non-existent container doesn't raise error."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.get.side_effect = NotFound("Container not found")
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        manager.remove_container("missing")  # Should not raise


class TestContainerManagerRemoveImage:
    """Tests for removing Docker images."""

    @patch("aibox.containers.manager.docker.from_env")
    def test_remove_image_success(self, mock_from_env: Mock) -> None:
        """Test successful image removal."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        result = manager.remove_image("aibox-test-claude:latest", force=False)

        assert result is True
        mock_client.images.remove.assert_called_once_with("aibox-test-claude:latest", force=False)

    @patch("aibox.containers.manager.docker.from_env")
    def test_remove_image_not_found(self, mock_from_env: Mock) -> None:
        """Test removing non-existent image returns False."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.images.remove.side_effect = ImageNotFound("Image not found")
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        result = manager.remove_image("missing:latest")

        assert result is False

    @patch("aibox.containers.manager.docker.from_env")
    def test_remove_image_in_use_raises_error(self, mock_from_env: Mock) -> None:
        """Test removing image in use raises DockerError."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.images.remove.side_effect = APIError("Image in use")
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        with pytest.raises(DockerError) as exc_info:
            manager.remove_image("in-use:latest")

        assert "Failed to remove image" in str(exc_info.value)

    @patch("aibox.containers.manager.docker.from_env")
    def test_remove_image_with_force(self, mock_from_env: Mock) -> None:
        """Test force removing image."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        result = manager.remove_image("aibox-test:latest", force=True)

        assert result is True
        mock_client.images.remove.assert_called_once_with("aibox-test:latest", force=True)


class TestContainerManagerExec:
    """Tests for executing commands in containers."""

    @patch("aibox.containers.manager.docker.from_env")
    def test_exec_in_container_success(self, mock_from_env: Mock) -> None:
        """Test successful command execution."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_from_env.return_value = mock_client

        mock_container = Mock()
        mock_container.exec_run.return_value = (0, b"output")

        manager = ContainerManager()
        exit_code, output = manager.exec_in_container(mock_container, "ls -la")

        assert exit_code == 0
        assert output == b"output"
        mock_container.exec_run.assert_called_once_with(
            "ls -la", workdir=None, user=None, demux=False
        )

    @patch("aibox.containers.manager.docker.from_env")
    def test_exec_in_container_with_workdir(self, mock_from_env: Mock) -> None:
        """Test command execution with working directory."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_from_env.return_value = mock_client

        mock_container = Mock()
        mock_container.exec_run.return_value = (0, b"")

        manager = ContainerManager()
        manager.exec_in_container(mock_container, "pwd", workdir="/tmp")

        mock_container.exec_run.assert_called_once_with(
            "pwd", workdir="/tmp", user=None, demux=False
        )

    @patch("aibox.containers.manager.docker.from_env")
    def test_exec_in_container_failure(self, mock_from_env: Mock) -> None:
        """Test command execution failure."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_from_env.return_value = mock_client

        mock_container = Mock()
        mock_container.exec_run.side_effect = APIError("Exec failed")

        manager = ContainerManager()
        with pytest.raises(DockerError):
            manager.exec_in_container(mock_container, "ls")


class TestContainerManagerUtilities:
    """Tests for utility methods."""

    @patch("aibox.containers.manager.docker.from_env")
    def test_container_exists_true(self, mock_from_env: Mock) -> None:
        """Test checking if container exists (true case)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.get.return_value = Mock()
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        assert manager.container_exists("test-container")

    @patch("aibox.containers.manager.docker.from_env")
    def test_container_exists_false(self, mock_from_env: Mock) -> None:
        """Test checking if container exists (false case)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.get.side_effect = NotFound("Not found")
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        assert not manager.container_exists("missing")

    @patch("aibox.containers.manager.docker.from_env")
    def test_is_container_running_true(self, mock_from_env: Mock) -> None:
        """Test checking if container is running (true case)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_container = Mock()
        mock_container.status = "running"
        mock_client.containers.get.return_value = mock_container
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        assert manager.is_container_running("test-container")

    @patch("aibox.containers.manager.docker.from_env")
    def test_is_container_running_false(self, mock_from_env: Mock) -> None:
        """Test checking if container is running (false case)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_container = Mock()
        mock_container.status = "exited"
        mock_client.containers.get.return_value = mock_container
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        assert not manager.is_container_running("test-container")

    @patch("aibox.containers.manager.docker.from_env")
    def test_is_container_running_not_found(self, mock_from_env: Mock) -> None:
        """Test checking if non-existent container is running."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.get.side_effect = NotFound("Not found")
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        assert not manager.is_container_running("missing")

    @patch("aibox.containers.manager.docker.from_env")
    def test_cleanup_stopped_containers(self, mock_from_env: Mock) -> None:
        """Test cleaning up stopped containers."""
        mock_client = Mock()
        mock_client.ping.return_value = True

        # Create mock containers
        running_container = Mock()
        running_container.status = "running"

        exited_container1 = Mock()
        exited_container1.status = "exited"

        exited_container2 = Mock()
        exited_container2.status = "exited"

        mock_client.containers.list.return_value = [
            running_container,
            exited_container1,
            exited_container2,
        ]
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        removed = manager.cleanup_stopped_containers("myproject")

        assert removed == 2
        running_container.remove.assert_not_called()
        exited_container1.remove.assert_called_once()
        exited_container2.remove.assert_called_once()


class TestContainerManagerImageManagement:
    """Tests for image management methods."""

    @patch("aibox.containers.manager.docker.from_env")
    def test_image_exists_true(self, mock_from_env: Mock) -> None:
        """Test checking if image exists (true case)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.images.get.return_value = Mock()
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        assert manager.image_exists("aibox-test:abc123")
        mock_client.images.get.assert_called_once_with("aibox-test:abc123")

    @patch("aibox.containers.manager.docker.from_env")
    def test_image_exists_false(self, mock_from_env: Mock) -> None:
        """Test checking if image exists (false case)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.images.get.side_effect = ImageNotFound("Image not found")
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        assert not manager.image_exists("missing:tag")

    @patch("aibox.containers.manager.docker.from_env")
    def test_tag_image_success(self, mock_from_env: Mock) -> None:
        """Test successful image tagging."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_image = Mock()
        mock_client.images.get.return_value = mock_image
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        manager.tag_image("aibox-test:abc123", "aibox-test:latest")

        mock_client.images.get.assert_called_once_with("aibox-test:abc123")
        mock_image.tag.assert_called_once_with("aibox-test", "latest")

    @patch("aibox.containers.manager.docker.from_env")
    def test_tag_image_without_tag(self, mock_from_env: Mock) -> None:
        """Test tagging image without explicit tag (defaults to latest)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_image = Mock()
        mock_client.images.get.return_value = mock_image
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        manager.tag_image("aibox-test:abc123", "aibox-test")

        mock_image.tag.assert_called_once_with("aibox-test", "latest")

    @patch("aibox.containers.manager.docker.from_env")
    def test_tag_image_source_not_found(self, mock_from_env: Mock) -> None:
        """Test tagging when source image doesn't exist."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.images.get.side_effect = ImageNotFound("Source not found")
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        with pytest.raises(DockerError) as exc_info:
            manager.tag_image("missing:tag", "new:tag")

        assert "Source image not found" in str(exc_info.value)

    @patch("aibox.containers.manager.docker.from_env")
    def test_prune_dangling_images_success(self, mock_from_env: Mock) -> None:
        """Test successful pruning of dangling images."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.images.prune.return_value = {
            "ImagesDeleted": [{"Deleted": "sha256:abc123"}, {"Deleted": "sha256:def456"}],
            "SpaceReclaimed": 1024 * 1024 * 100,  # 100 MB
        }
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        result = manager.prune_dangling_images()

        assert len(result["ImagesDeleted"]) == 2
        assert result["SpaceReclaimed"] == 1024 * 1024 * 100
        mock_client.images.prune.assert_called_once_with(filters={"dangling": True})

    @patch("aibox.containers.manager.docker.from_env")
    def test_prune_dangling_images_with_filters(self, mock_from_env: Mock) -> None:
        """Test pruning dangling images with additional filters."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.images.prune.return_value = {"ImagesDeleted": [], "SpaceReclaimed": 0}
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        additional_filters = {"label": "project=test"}
        manager.prune_dangling_images(filters=additional_filters)

        expected_filters = {"dangling": True, "label": "project=test"}
        mock_client.images.prune.assert_called_once_with(filters=expected_filters)

    @patch("aibox.containers.manager.docker.from_env")
    def test_prune_dangling_images_api_error(self, mock_from_env: Mock) -> None:
        """Test pruning dangling images with API error."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.images.prune.side_effect = APIError("Prune failed")
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        with pytest.raises(DockerError) as exc_info:
            manager.prune_dangling_images()

        assert "Failed to prune dangling images" in str(exc_info.value)

    @patch("aibox.containers.manager.docker.from_env")
    def test_list_images_success(self, mock_from_env: Mock) -> None:
        """Test listing images."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_images = [Mock(), Mock(), Mock()]
        mock_client.images.list.return_value = mock_images
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        images = manager.list_images()

        assert images == mock_images
        mock_client.images.list.assert_called_once_with(filters=None)

    @patch("aibox.containers.manager.docker.from_env")
    def test_list_images_with_filters(self, mock_from_env: Mock) -> None:
        """Test listing images with filters."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.images.list.return_value = []
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        filters = {"reference": "aibox-*"}
        manager.list_images(filters=filters)

        mock_client.images.list.assert_called_once_with(filters=filters)

    @patch("aibox.containers.manager.docker.from_env")
    def test_list_images_api_error(self, mock_from_env: Mock) -> None:
        """Test listing images with API error."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.images.list.side_effect = APIError("List failed")
        mock_from_env.return_value = mock_client

        manager = ContainerManager()
        images = manager.list_images()

        assert images == []
