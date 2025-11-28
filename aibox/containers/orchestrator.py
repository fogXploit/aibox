"""
Container orchestration layer.

This module coordinates all aibox services to provide high-level
container lifecycle operations. It acts as the business logic layer
between CLI commands and low-level services.

The orchestrator:
- Loads and validates configuration
- Selects and validates AI providers
- Manages slot assignment
- Generates Dockerfiles from profiles
- Builds images and starts containers
- Handles errors with helpful context

This keeps CLI commands thin and focused on user interaction,
while keeping low-level services (Docker SDK, config loading)
simple and reusable.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from aibox.config.loader import load_config
from aibox.containers.manager import ContainerManager
from aibox.containers.slot import SlotManager
from aibox.containers.volumes import VolumeManager
from aibox.profiles.generator import DockerfileGenerator
from aibox.profiles.loader import ProfileLoader
from aibox.providers.registry import ProviderRegistry
from aibox.utils.hash import get_project_storage_dir


@dataclass
class ContainerInfo:
    """
    Information about a started container.

    This is returned by start_container() to provide details
    about the container that was created.
    """

    container_id: str
    container_name: str
    slot_number: int
    ai_provider: str
    project_name: str


class ContainerOrchestrator:
    """
    Orchestrates container lifecycle operations.

    This class coordinates all aibox subsystems to provide
    high-level operations like starting and stopping containers.
    It handles the business logic and error handling, delegating
    to specialized services for specific tasks.

    Example:
        >>> orchestrator = ContainerOrchestrator()
        >>> info = orchestrator.start_container(
        ...     project_root=Path.cwd(),
        ...     ai_provider="claude",
        ...     slot_number=1
        ... )
        >>> print(f"Started {info.container_name} in slot {info.slot_number}")
    """

    @staticmethod
    def _generate_base_image_hash(
        dockerfile_content: str,
        base_image: str,
        profiles: list[str],
    ) -> str:
        """
        Hash for the provider-agnostic base image (profiles only).

        Includes Dockerfile content, base image, and normalized profile list.
        """
        content_parts = [
            dockerfile_content,
            base_image,
            ",".join(sorted(profiles)),
        ]
        content_str = "\n".join(content_parts)
        hash_obj = hashlib.sha256(content_str.encode("utf-8"))
        return hash_obj.hexdigest()[:12]

    @staticmethod
    def _generate_provider_image_hash(
        dockerfile_content: str,
        provider_name: str,
        base_hash: str,
    ) -> str:
        """
        Hash for provider-specific layer built on a base image.

        Ties together provider layer content, provider name, and the base hash
        so changes in either trigger a rebuild.
        """
        content_parts = [
            dockerfile_content,
            provider_name,
            base_hash,
        ]
        content_str = "\n".join(content_parts)
        hash_obj = hashlib.sha256(content_str.encode("utf-8"))
        return hash_obj.hexdigest()[:12]

    def start_container(
        self,
        project_root: Path,
        slot_number: int | None = None,
        ai_provider: str | None = None,
        reuse_existing: bool = True,
        auto_remove: bool = True,
        force_openai_auth_port: bool = False,
        progress_callback: Callable[[str], None] | None = None,
    ) -> ContainerInfo:
        """
        Start a container for the project with per-slot configuration.

        This orchestrates the full container startup:
        1. Load configuration
        2. Assign slot (auto or manual)
        3. Get AI provider from slot config (or use provided one for new slots)
        4. Validate AI provider
        5. Generate Dockerfile from profiles
        6. Build Docker image
        7. Prepare per-slot volumes (project + slot metadata + provider config)
        8. Create and start container
        9. Save slot metadata

        Args:
            project_root: Project root directory
            slot_number: Slot number 1-10 (auto-assigns if None)
            ai_provider: AI provider name for configuring new slots (internal use)
            reuse_existing: Reuse a running/stopped container for the slot if present
            auto_remove: Use Docker auto-remove when the container stops (one-off sessions)
            progress_callback: Optional callback function(line: str) for build progress

        Returns:
            ContainerInfo with details about started container

        Raises:
            ConfigNotFoundError: If configuration is missing
            ProviderNotFoundError: If provider is unknown
            APIKeyNotFoundError: If API key is missing
            NoAvailableSlotsError: If all slots are in use
            ImageBuildError: If Docker image build fails
            ContainerStartError: If container fails to start
        """
        # Step 1: Load configuration
        config = load_config(str(project_root))
        storage_dir = get_project_storage_dir(project_root)

        # Step 2: Assign slot early (needed for config merging)
        slot_manager = SlotManager(storage_dir)
        if slot_number is None:
            slot_number = slot_manager.find_available_slot()

        # Step 3: Determine AI provider from slot configuration
        # ai_provider parameter is only used when configuring a new slot
        provider_name: str
        if ai_provider:
            # Setting up a new slot with specified provider
            provider_name = ai_provider
        else:
            # Get provider from existing slot configuration
            slot_config = slot_manager.get_slot(slot_number)
            preconfigured_provider = slot_config.get_ai_provider()

            if preconfigured_provider:
                provider_name = preconfigured_provider
            else:
                # No provider specified - this shouldn't happen as the CLI should prompt
                from aibox.utils.errors import AiboxError

                raise AiboxError(
                    "No AI provider specified for slot",
                    suggestion=f"Configure slot {slot_number} with 'aibox slot add --slot {slot_number}' or run 'aibox start' without --slot to use the interactive wizard",
                )

        # Step 4: Get and validate provider
        provider = ProviderRegistry.get_provider(provider_name)
        provider.validate_config(config)

        # Step 4: Load profiles and generate Dockerfile
        profile_loader = ProfileLoader()
        profiles_with_versions = [
            profile_loader.load_profile(profile_spec) for profile_spec in config.project.profiles
        ]

        dockerfile_generator = DockerfileGenerator(
            base_image=config.global_config.docker.base_image
        )
        base_dockerfile = dockerfile_generator.generate(
            profiles_with_versions=profiles_with_versions,
            ai_provider=None,
        )
        base_build_args = dockerfile_generator.generate_build_args(profiles_with_versions)

        # Step 5: Build/reuse provider-agnostic base image
        container_manager = ContainerManager()

        base_hash = self._generate_base_image_hash(
            dockerfile_content=base_dockerfile,
            base_image=config.global_config.docker.base_image,
            profiles=config.project.profiles,
        )
        base_tag_hash = f"aibox-{config.project.name}-base:{base_hash}"
        base_tag_latest = f"aibox-{config.project.name}-base:latest"

        self._ensure_image_exists(
            container_manager=container_manager,
            image_tag_hash=base_tag_hash,
            image_tag_latest=base_tag_latest,
            dockerfile_content=base_dockerfile,
            buildargs=base_build_args,
            progress_callback=progress_callback,
            image_description="base image",
        )

        # Step 6: Build/reuse provider layer on top of cached base
        provider_dockerfile = dockerfile_generator.generate_provider_layer(
            base_tag=base_tag_hash, ai_provider=provider_name
        )

        provider_hash = self._generate_provider_image_hash(
            dockerfile_content=provider_dockerfile,
            provider_name=provider_name,
            base_hash=base_hash,
        )
        provider_tag_hash = f"aibox-{config.project.name}-{provider_name}:{provider_hash}"
        provider_tag_latest = f"aibox-{config.project.name}-{provider_name}:latest"

        provider_build_occurred = self._ensure_image_exists(
            container_manager=container_manager,
            image_tag_hash=provider_tag_hash,
            image_tag_latest=provider_tag_latest,
            dockerfile_content=provider_dockerfile,
            cache_from=[base_tag_hash, base_tag_latest, provider_tag_latest],
            progress_callback=progress_callback,
            image_description="provider image",
        )

        if provider_build_occurred:
            # Clean up dangling images after successful provider build
            if progress_callback:
                progress_callback("Cleaning up dangling images...\n")

            prune_result = container_manager.prune_dangling_images()
            images_deleted = prune_result.get("ImagesDeleted") or []
            space_reclaimed = prune_result.get("SpaceReclaimed", 0)

            if progress_callback and images_deleted:
                space_mb = space_reclaimed / (1024 * 1024)
                progress_callback(
                    f"✓ Removed {len(images_deleted)} dangling image(s), "
                    f"reclaimed {space_mb:.1f} MB\n"
                )

        # Use provider :latest tag for container creation
        image_tag = provider_tag_latest

        # Step 6: Prepare volumes with per-slot provider directories
        volume_manager = VolumeManager(project_dir=project_root, project_storage_dir=storage_dir)
        all_volumes = volume_manager.prepare_volumes(
            slot_number=slot_number, provider=provider, custom_mounts=config.project.mounts
        )

        # Step 7: Get environment variables and ports from provider
        env_vars = provider.get_docker_env_vars()
        ports = provider.get_required_ports(
            force_auth_port=force_openai_auth_port,
            project_storage_dir=storage_dir,
            slot_number=slot_number,
        )

        # Step 8: Create/reuse and start container
        container_name = f"aibox-{config.project.name}-{slot_number}"
        container = None
        existing_container = container_manager.get_container(container_name)

        if reuse_existing and existing_container:
            if container_manager.is_container_running(container_name):
                container = existing_container
                if progress_callback:
                    progress_callback(
                        f"✓ Reusing running container '{container_name}' for slot {slot_number}\n"
                    )
            else:
                # Restart existing container to preserve its filesystem state
                container_manager.start_container(existing_container)
                container = existing_container
                if progress_callback:
                    progress_callback(
                        f"✓ Restarted existing container '{container_name}' for slot {slot_number}\n"
                    )

        if container is None:
            container = container_manager.create_container(
                image=image_tag,
                name=container_name,
                volumes=all_volumes,
                environment=env_vars,
                ports=ports or None,
                auto_remove=auto_remove,
            )
            container_manager.start_container(container)

        # Step 9: Save slot metadata
        runtime_slot = slot_manager.get_slot(slot_number)
        runtime_slot.save(
            ai_provider=provider_name,
            container_name=container_name,
        )

        return ContainerInfo(
            container_id=container.id,
            container_name=container_name,
            slot_number=slot_number,
            ai_provider=provider_name,
            project_name=config.project.name,
        )

    def _ensure_image_exists(
        self,
        container_manager: ContainerManager,
        image_tag_hash: str,
        image_tag_latest: str,
        dockerfile_content: str,
        buildargs: dict[str, str] | None = None,
        cache_from: list[str] | None = None,
        progress_callback: Callable[[str], None] | None = None,
        image_description: str = "image",
    ) -> bool:
        """
        Ensure image exists, building if necessary. Returns True if a build occurred.
        """
        build_occurred = False
        hash_short = image_tag_hash.split(":")[-1]

        if container_manager.image_exists(image_tag_hash):
            if progress_callback:
                progress_callback(
                    f"✓ Reusing {image_description} with hash {hash_short} (cached)\n"
                )
            try:
                container_manager.tag_image(image_tag_hash, image_tag_latest)
            except Exception:
                if progress_callback:
                    progress_callback(
                        f"{image_description} :latest tag missing, retagging after rebuild...\n"
                    )
                self._build_image(
                    container_manager=container_manager,
                    dockerfile_content=dockerfile_content,
                    image_tag_hash=image_tag_hash,
                    buildargs=buildargs,
                    cache_from=cache_from,
                    progress_callback=progress_callback,
                )
                container_manager.tag_image(image_tag_hash, image_tag_latest)
                build_occurred = True
        else:
            self._build_image(
                container_manager=container_manager,
                dockerfile_content=dockerfile_content,
                image_tag_hash=image_tag_hash,
                buildargs=buildargs,
                cache_from=cache_from,
                progress_callback=progress_callback,
            )
            if not container_manager.image_exists(image_tag_hash):
                from aibox.utils.errors import ImageBuildError

                raise ImageBuildError(
                    message=f"Image build did not produce tag {image_tag_hash}",
                    suggestion="Check Docker build logs for failures",
                )
            container_manager.tag_image(image_tag_hash, image_tag_latest)
            build_occurred = True

        return build_occurred

    def _build_image(
        self,
        container_manager: ContainerManager,
        dockerfile_content: str,
        image_tag_hash: str,
        buildargs: dict[str, str] | None = None,
        cache_from: list[str] | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Build image from Dockerfile content and tag with hash."""
        if progress_callback:
            progress_callback(f"Building new image with hash {image_tag_hash.split(':')[-1]}...\n")

        with TemporaryDirectory() as tmpdir:
            dockerfile_path = Path(tmpdir) / "Dockerfile"
            dockerfile_path.write_text(dockerfile_content)

            container_manager.build_image(
                dockerfile_path=tmpdir,
                tag=image_tag_hash,
                buildargs=buildargs,
                cache_from=cache_from,
                progress_callback=progress_callback,
            )

    def stop_container(
        self,
        project_root: Path,
        slot_number: int,
    ) -> None:
        """
        Stop a container by slot number.

        Args:
            project_root: Project root directory
            slot_number: Slot number (1-10)

        Raises:
            SlotNotFoundError: If slot doesn't exist
            DockerError: If container stop fails
        """
        # Load config to get project name
        config = load_config(str(project_root))
        storage_dir = get_project_storage_dir(project_root)

        # Get slot info to find container name
        slot_manager = SlotManager(storage_dir)
        slot_config = slot_manager.get_slot(slot_number)
        slot_data = slot_config.load()

        container_name = slot_data.get("container_name") if slot_data else None
        if not container_name:
            # Fallback: construct name from config
            container_name = f"aibox-{config.project.name}-{slot_number}"

        # Stop container
        container_manager = ContainerManager()
        container_manager.stop_container(container_name)

        # Note: Slot metadata is preserved when container is stopped.
        # Users can explicitly clean up slots with 'aibox slot cleanup' if desired.

    def attach_to_container(
        self,
        project_root: Path,
        slot_number: int | None = None,
        resume: bool = False,
    ) -> int:
        """
        Attach to a running container's AI CLI interactively.

        This connects to the container and starts the AI CLI in interactive mode,
        giving the user full TTY access. The command to run is determined by the
        AI provider configured for the slot.

        Args:
            project_root: Project root directory
            slot_number: Slot number (1-10). If None, attaches to first running slot.

        Returns:
            Exit code from AI CLI session

        Raises:
            SlotNotFoundError: If slot doesn't exist or no running slots found
            DockerError: If attach fails
        """
        # Load config and get slot info
        load_config(str(project_root))
        storage_dir = get_project_storage_dir(project_root)
        slot_manager = SlotManager(storage_dir)

        # If no slot specified, find first running slot
        if slot_number is None:
            container_manager = ContainerManager()
            slots_list = slot_manager.list_slots()

            for slot in slots_list:
                container_name = slot.get("container_name", "")
                if container_manager.is_container_running(container_name):
                    slot_number = slot["slot"]
                    break

            if slot_number is None:
                from aibox.utils.errors import SlotNotFoundError

                raise SlotNotFoundError(
                    "No running containers found",
                    suggestion="Start a container first with: aibox start",
                )

        # Get slot config
        slot_config = slot_manager.get_slot(slot_number)
        slot_data = slot_config.load()

        if not slot_data:
            from aibox.utils.errors import SlotNotFoundError

            raise SlotNotFoundError(
                f"Slot {slot_number} not found",
                suggestion="Check available slots with: aibox slot list",
            )

        container_name = slot_data.get("container_name", "")
        ai_provider_name = slot_data.get("ai_provider", "")

        # Get AI provider and its CLI command
        provider = ProviderRegistry.get_provider(ai_provider_name)
        cli_command = provider.get_cli_command()

        # Optional Codex resume: only override when requested and a session exists.
        if (
            resume
            and provider.name == "openai"
            and self._slot_has_codex_session(
                project_storage_dir=storage_dir, slot_number=slot_number
            )
        ):
            cli_command = ["codex", "resume"]

        # Attach interactively
        container_manager = ContainerManager()
        return container_manager.attach_interactive(container_name, cli_command)

    @staticmethod
    def _slot_has_codex_session(project_storage_dir: str | Path, slot_number: int) -> bool:
        """
        Check for an existing Codex session in the slot-scoped .codex directory.
        """
        codex_dir = (
            Path.home()
            / ".aibox"
            / "projects"
            / str(project_storage_dir)
            / "slots"
            / f"slot-{slot_number}"
            / ".codex"
        )
        if not codex_dir.exists():
            return False

        known_files = [
            codex_dir / "config.json",
            codex_dir / "config",
            codex_dir / "session.json",
        ]

        for file_path in known_files:
            try:
                if file_path.exists() and file_path.stat().st_size > 0:
                    return True
            except OSError:
                continue

        try:
            return any(p.is_file() and p.stat().st_size > 0 for p in codex_dir.iterdir())
        except OSError:
            return False
