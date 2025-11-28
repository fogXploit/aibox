"""
Docker container lifecycle management.

Handles building images, creating containers, and managing container lifecycle
using the Python Docker SDK.
"""

import subprocess
from collections.abc import Callable
from typing import Any

import docker
from docker import DockerClient
from docker.errors import APIError, DockerException, ImageNotFound, NotFound
from docker.models.containers import Container

from aibox.utils.errors import (
    ContainerStartError,
    DockerError,
    DockerNotFoundError,
    ImageBuildError,
)


class ContainerManager:
    """Manages Docker container lifecycle for aibox."""

    def __init__(self) -> None:
        """
        Initialize container manager.

        Raises:
            DockerNotFoundError: If Docker is not running or accessible
        """
        try:
            self.client: DockerClient = docker.from_env()
            # Verify connection
            self.client.ping()
        except DockerException as e:
            raise DockerNotFoundError(
                message="Docker is not running or not accessible",
                suggestion="Start Docker and ensure it's accessible. Run: docker ps",
            ) from e

    def build_image(
        self,
        dockerfile_path: str,
        tag: str,
        buildargs: dict[str, str] | None = None,
        nocache: bool = False,
        pull: bool = False,
        cache_from: list[str] | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        """
        Build Docker image with caching and optional progress streaming.

        Args:
            dockerfile_path: Path to directory containing Dockerfile
            tag: Image tag name
            buildargs: Build-time variables
            nocache: If True, don't use cache
            pull: If True, always attempt to pull base image layers
            cache_from: List of cache source image tags
            progress_callback: Optional callback function(line: str) for build progress

        Raises:
            ImageBuildError: If image build fails
        """
        try:
            # Build with streaming output
            build_logs = self.client.api.build(
                path=dockerfile_path,
                tag=tag,
                buildargs=buildargs or {},
                rm=True,  # Remove intermediate containers
                pull=pull,  # Pull base images only when requested
                nocache=nocache,
                cache_from=cache_from or [],
                decode=True,  # Decode JSON stream
            )

            # Process build logs
            for chunk in build_logs:
                if progress_callback:
                    # Extract stream or error from chunk
                    if "stream" in chunk:
                        progress_callback(chunk["stream"])
                    elif "error" in chunk:
                        # Error during build
                        error_msg = chunk.get("error", "")
                        progress_callback(f"ERROR: {error_msg}")
                        raise ImageBuildError(
                            message=f"Failed to build image '{tag}': {error_msg}",
                            suggestion="Check Dockerfile syntax and ensure base images are accessible",
                        )
                    elif "errorDetail" in chunk:
                        error_msg = chunk.get("errorDetail", {}).get("message", "")
                        progress_callback(f"ERROR: {error_msg}")
                        raise ImageBuildError(
                            message=f"Failed to build image '{tag}': {error_msg}",
                            suggestion="Check Dockerfile syntax and ensure base images are accessible",
                        )
                    elif "status" in chunk:
                        # Status updates (pulling images, etc)
                        status = chunk.get("status", "")
                        progress = chunk.get("progress", "")
                        if progress:
                            progress_callback(f"{status} {progress}\n")
                        else:
                            progress_callback(f"{status}\n")

        except ImageBuildError:
            # Re-raise ImageBuildError as-is
            raise
        except (APIError, DockerException) as e:
            raise ImageBuildError(
                message=f"Failed to build image '{tag}': {e}",
                suggestion="Check Dockerfile syntax and ensure base images are accessible",
            ) from e

    def create_container(
        self,
        image: str,
        name: str,
        volumes: dict[str, dict[str, str]],
        environment: dict[str, str] | None = None,
        command: list[str] | str | None = None,
        working_dir: str = "/workspace",
        ports: dict[str, tuple[str, int]] | dict[str, int] | dict[int, int] | None = None,
        network_mode: str | None = None,
        auto_remove: bool = True,
    ) -> Container:
        """
        Create container with auto-remove flag.

        Args:
            image: Docker image name
            name: Container name
            volumes: Volume mounts {host_path: {bind: container_path, mode: rw|ro}}
            environment: Environment variables
            command: Command to run (optional)
            working_dir: Working directory in container
            ports: Port mappings {container_port: host_port} for OAuth callbacks

        Returns:
            Created Container instance

        Raises:
            ContainerStartError: If container creation fails
        """
        try:
            container: Container = self.client.containers.create(
                image=image,
                name=name,
                volumes=volumes,
                environment=environment or {},
                command=command,
                working_dir=working_dir,
                ports=ports or {},  # Publish ports for OAuth authentication
                network_mode=network_mode,
                auto_remove=auto_remove,  # Allow callers to persist containers when needed
                detach=True,  # Run in background
                stdin_open=True,  # Keep stdin open
                tty=True,  # Allocate pseudo-TTY
            )
            return container
        except ImageNotFound as e:
            raise ContainerStartError(
                message=f"Image not found: {image}",
                suggestion=f"Build the image first: docker build -t {image} .",
            ) from e
        except (APIError, DockerException) as e:
            raise ContainerStartError(
                message=f"Failed to create container '{name}': {e}",
                suggestion="Check container name isn't already in use and image exists",
            ) from e

    def start_container(self, container: Container) -> None:
        """
        Start a created container.

        Args:
            container: Container instance to start

        Raises:
            ContainerStartError: If container fails to start
        """
        try:
            container.start()
        except (APIError, DockerException) as e:
            raise ContainerStartError(
                message=f"Failed to start container '{container.name}': {e}",
                suggestion="Check Docker logs for details",
            ) from e

    def get_container(self, name: str) -> Container | None:
        """
        Get container by name.

        Args:
            name: Container name

        Returns:
            Container instance, or None if not found
        """
        try:
            return self.client.containers.get(name)
        except NotFound:
            return None
        except (APIError, DockerException):
            return None

    def list_containers(
        self, all_containers: bool = True, filters: dict[str, Any] | None = None
    ) -> list[Container]:
        """
        List containers.

        Args:
            all_containers: If True, include stopped containers
            filters: Filter criteria (e.g., {"name": "aibox-"})

        Returns:
            List of Container instances
        """
        try:
            containers: list[Container] = self.client.containers.list(
                all=all_containers, filters=filters
            )
            return containers
        except (APIError, DockerException):
            return []

    def stop_container(self, name: str, timeout: int = 10) -> None:
        """
        Stop a running container.

        Args:
            name: Container name
            timeout: Seconds to wait before killing container

        Raises:
            DockerError: If container doesn't exist or stop fails
        """
        try:
            container = self.client.containers.get(name)
            container.stop(timeout=timeout)
        except NotFound as e:
            raise DockerError(
                message=f"Container not found: {name}",
                suggestion="Check container name with: docker ps -a",
            ) from e
        except (APIError, DockerException) as e:
            raise DockerError(
                message=f"Failed to stop container '{name}': {e}",
                suggestion="Try: docker stop {name}",
            ) from e

    def remove_container(self, name: str, force: bool = False) -> None:
        """
        Remove a container.

        Args:
            name: Container name
            force: If True, force remove even if running

        Raises:
            DockerError: If container doesn't exist or removal fails
        """
        try:
            container = self.client.containers.get(name)
            container.remove(force=force)
        except NotFound:
            # Already removed, no error
            pass
        except (APIError, DockerException) as e:
            raise DockerError(
                message=f"Failed to remove container '{name}': {e}",
                suggestion="Try: docker rm -f {name}",
            ) from e

    def remove_image(self, tag: str, force: bool = False) -> bool:
        """
        Remove a Docker image.

        Args:
            tag: Image tag name (e.g., "aibox-myproject-claude:latest")
            force: If True, force remove even if image is in use

        Returns:
            True if image was removed, False if image didn't exist

        Raises:
            DockerError: If image removal fails
        """
        try:
            self.client.images.remove(tag, force=force)
            return True
        except ImageNotFound:
            # Image already removed or never existed
            return False
        except (APIError, DockerException) as e:
            # Image might be in use by another container
            raise DockerError(
                message=f"Failed to remove image '{tag}': {e}",
                suggestion="Check if image is in use: docker images | grep {tag}",
            ) from e

    def image_exists(self, tag: str) -> bool:
        """
        Check if a Docker image exists.

        Args:
            tag: Image tag name (e.g., "aibox-myproject-claude:abc123")

        Returns:
            True if image exists, False otherwise
        """
        try:
            self.client.images.get(tag)
            return True
        except ImageNotFound:
            return False
        except (APIError, DockerException):
            return False

    def is_image_in_use(self, tag: str) -> bool:
        """
        Check if any containers are using the image.

        Args:
            tag: Image tag name

        Returns:
            True if at least one container uses the image, False otherwise.
            Returns True on Docker errors to avoid accidental removals.
        """
        try:
            containers = self.client.containers.list(all=True, filters={"ancestor": tag})
            return len(containers) > 0
        except (APIError, DockerException):
            return True

    def tag_image(self, source_tag: str, target_tag: str) -> None:
        """
        Tag an existing image with a new tag.

        Args:
            source_tag: Existing image tag
            target_tag: New tag to apply

        Raises:
            DockerError: If tagging fails
        """
        try:
            image = self.client.images.get(source_tag)
            # Split target_tag into repository and tag
            if ":" in target_tag:
                repository, tag = target_tag.rsplit(":", 1)
            else:
                repository = target_tag
                tag = "latest"
            image.tag(repository, tag)
        except ImageNotFound as e:
            raise DockerError(
                message=f"Source image not found: {source_tag}",
                suggestion="Build the image first",
            ) from e
        except (APIError, DockerException) as e:
            raise DockerError(
                message=f"Failed to tag image '{source_tag}' as '{target_tag}': {e}",
                suggestion="Check if source image exists",
            ) from e

    def prune_dangling_images(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Remove dangling images (untagged images with <none> tag).

        Args:
            filters: Additional filter criteria (e.g., {"label": "project=myproject"})

        Returns:
            Dict with pruning results containing:
                - ImagesDeleted: List of deleted image IDs
                - SpaceReclaimed: Bytes reclaimed

        Raises:
            DockerError: If pruning fails
        """
        try:
            # Always filter for dangling images
            prune_filters = {"dangling": True}
            if filters:
                prune_filters.update(filters)

            result: dict[str, Any] = self.client.images.prune(filters=prune_filters)
            return result
        except (APIError, DockerException) as e:
            raise DockerError(
                message=f"Failed to prune dangling images: {e}",
                suggestion="Try: docker image prune",
            ) from e

    def list_images(self, filters: dict[str, Any] | None = None) -> list[Any]:
        """
        List Docker images.

        Args:
            filters: Filter criteria (e.g., {"reference": "aibox-*"})

        Returns:
            List of Image objects
        """
        try:
            images: list[Any] = self.client.images.list(filters=filters)
            return images
        except (APIError, DockerException):
            return []

    def exec_in_container(
        self,
        container: Container,
        command: str | list[str],
        workdir: str | None = None,
        user: str | None = None,
    ) -> tuple[int, bytes]:
        """
        Execute command in running container.

        Args:
            container: Container instance
            command: Command to execute
            workdir: Working directory for command
            user: User to run command as (e.g., "root" or "aibox")

        Returns:
            Tuple of (exit_code, output)

        Raises:
            DockerError: If execution fails
        """
        try:
            exit_code, output = container.exec_run(command, workdir=workdir, user=user, demux=False)
            return exit_code, output
        except (APIError, DockerException) as e:
            raise DockerError(
                message=f"Failed to execute command in container: {e}",
                suggestion="Ensure container is running",
            ) from e

    def cleanup_stopped_containers(self, project_name: str) -> int:
        """
        Clean up stopped containers for a project.

        Args:
            project_name: Project name to filter containers

        Returns:
            Number of containers removed
        """
        filters = {"name": f"aibox-{project_name}"}
        containers = self.list_containers(all_containers=True, filters=filters)

        removed = 0
        for container in containers:
            if container.status in ("exited", "dead", "created"):
                try:
                    container.remove()
                    removed += 1
                except (APIError, DockerException):
                    # Skip containers that can't be removed
                    continue

        return removed

    def container_exists(self, name: str) -> bool:
        """
        Check if a container exists.

        Args:
            name: Container name

        Returns:
            True if container exists, False otherwise
        """
        return self.get_container(name) is not None

    def is_container_running(self, name: str) -> bool:
        """
        Check if a container is running.

        Args:
            name: Container name

        Returns:
            True if container is running, False otherwise
        """
        container = self.get_container(name)
        if container is None:
            return False
        status: str = str(container.status)
        return status == "running"

    def attach_interactive(self, name: str, command: list[str]) -> int:
        """
        Execute command in container with interactive TTY.

        This uses subprocess to call docker exec -it, which provides
        full TTY support for interactive commands like AI CLIs.

        Args:
            name: Container name
            command: Command to execute (e.g., ["claude"] or ["bash"])

        Returns:
            Exit code from command

        Raises:
            DockerError: If command execution fails
        """
        try:
            # Use docker exec -it for full TTY support
            cmd = ["docker", "exec", "-it", name] + command
            result = subprocess.run(cmd, check=False)
            return result.returncode
        except FileNotFoundError as e:
            raise DockerError(
                message="Docker command not found",
                suggestion="Ensure docker is in your PATH",
            ) from e
        except Exception as e:
            raise DockerError(
                message=f"Failed to execute command in container: {e}",
                suggestion="Ensure container is running",
            ) from e
