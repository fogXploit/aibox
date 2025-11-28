"""
Slot management commands.

Provides commands to list and cleanup container slots.
Slots are managed automatically via runtime metadata.
"""

import contextlib
import sys
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

from rich.console import Console
from rich.live import Live
from rich.prompt import Confirm, IntPrompt
from rich.table import Table
from rich.text import Text

from aibox.cli.commands.start import _select_provider
from aibox.config.loader import load_config, load_project_config
from aibox.config.models import Config
from aibox.containers.manager import ContainerManager
from aibox.containers.orchestrator import ContainerOrchestrator
from aibox.containers.slot import SlotManager
from aibox.containers.volumes import VolumeManager
from aibox.profiles.generator import DockerfileGenerator
from aibox.profiles.loader import ProfileLoader
from aibox.providers.base import AIProvider
from aibox.providers.registry import ProviderRegistry
from aibox.utils.errors import ConfigNotFoundError, DockerNotFoundError
from aibox.utils.hash import get_project_storage_dir

console = Console()


def slot_list(project_root: Path) -> None:
    """
    List all slots for the project.

    Shows a table with slot numbers, status, and container information.

    Args:
        project_root: Project root directory
    """
    try:
        storage_dir = get_project_storage_dir(project_root)
        slot_manager = SlotManager(storage_dir)
        slots_list = slot_manager.list_slots()

        # Load profiles from project config
        try:
            project_config = load_project_config(str(project_root))
            profiles_list = project_config.profiles
            profiles_display = ", ".join(profiles_list) if profiles_list else "[dim]-[/dim]"
        except Exception:
            # If config can't be loaded, show N/A
            profiles_display = "[dim]N/A[/dim]"

        # Convert list to dict keyed by slot number
        slots_dict = {slot["slot"]: slot for slot in slots_list}

        # Create table
        table = Table(title="[bold]Container Slots[/bold]", show_lines=False)
        table.add_column("Slot", style="cyan", justify="center")
        table.add_column("Status", style="white")
        table.add_column("Container", style="green")
        table.add_column("AI Provider", style="blue")
        table.add_column("Profiles", style="magenta")

        if not slots_list:
            console.print("\n[yellow]No active slots[/yellow]\n")
            console.print("Run [cyan]aibox start[/cyan] to create a container\n")
            return

        # Initialize container manager to check actual Docker state
        try:
            container_manager = ContainerManager()
        except DockerNotFoundError:
            # If Docker is not available, fall back to metadata-only display
            container_manager = None

        # Show only existing slots (dynamic list)
        for slot_num in sorted(slots_dict.keys()):
            slot_info = slots_dict[slot_num]
            container_name = slot_info.get("container_name", "N/A")
            ai_provider = slot_info.get("ai_provider", "N/A")

            # Check actual Docker container status
            if container_manager and container_manager.is_container_running(container_name):
                status = "[green]●[/green] Running"
            else:
                status = "[yellow]⏸[/yellow] Stopped"

            table.add_row(
                str(slot_num),
                status,
                container_name,
                ai_provider,
                profiles_display,
            )

        # Count running containers
        running_count = 0
        if container_manager:
            for slot in slots_list:
                container_name = slot.get("container_name", "")
                if container_manager.is_container_running(container_name):
                    running_count += 1

        console.print()
        console.print(table)
        if container_manager:
            console.print(
                f"\n[dim]Running: {running_count}/{len(slots_list)} | "
                f"Total slots: {len(slots_list)}[/dim]\n"
            )
        else:
            console.print(f"\n[dim]Total slots: {len(slots_list)}[/dim]\n")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


def slot_cleanup(project_root: Path, slot_number: int | None = None) -> None:
    """
    Clean up stopped container slots.

    Args:
        project_root: Project root directory
        slot_number: Optional slot number to clean up. If None, cleans up all slots.
    """
    try:
        storage_dir = get_project_storage_dir(project_root)
        slot_manager = SlotManager(storage_dir)

        if slot_number is not None:
            # Clean up single slot
            console.print(f"\n[bold blue]Cleaning up slot {slot_number}...[/bold blue]\n")

            with console.status(
                "[cyan]Cleaning up slot...[/cyan]",
                spinner="dots",
            ):
                slot_manager.cleanup_slot(slot_number)

            console.print(
                f"[bold green]✓[/bold green] Slot {slot_number} cleaned up successfully\n"
            )
        else:
            # Clean up all slots
            console.print("\n[bold blue]Cleaning up all stopped containers...[/bold blue]\n")

            with console.status(
                "[cyan]Cleaning up slots...[/cyan]",
                spinner="dots",
            ):
                slot_manager.cleanup_all_slots()

            console.print("[bold green]✓[/bold green] All slots cleaned up successfully\n")

    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠[/yellow]  Cancelled by user\n")
        raise SystemExit(1) from None
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


def slot_add(project_root: Path) -> None:
    """
    Add/configure a new slot with interactive wizard.

    Pre-configures a slot with a specific AI provider before starting it.
    Useful for setting up multiple slots with different AI providers.

    Args:
        project_root: Project root directory

    Raises:
        ConfigNotFoundError: If project is not initialized
        SystemExit: If user cancels or validation fails
    """
    try:
        # Verify project is initialized
        try:
            load_project_config(str(project_root))
        except ConfigNotFoundError:
            console.print("\n[red]✗[/red] Project not initialized\n")
            console.print("[bold]💡 Solution:[/bold] Run 'aibox init' first\n")
            raise SystemExit(1) from None

        # Get storage directory
        storage_dir = get_project_storage_dir(project_root)
        slot_manager = SlotManager(storage_dir)

        # Get list of occupied slots from runtime metadata
        slots_list = slot_manager.list_slots()
        occupied_slots = {slot["slot"] for slot in slots_list}

        console.print("\n[bold blue]Configure New Slot[/bold blue]\n")

        # Show currently occupied slots
        if occupied_slots:
            console.print(
                f"[dim]Occupied slots: {', '.join(map(str, sorted(occupied_slots)))}[/dim]\n"
            )

        # Get next available slot number
        try:
            from aibox.utils.errors import NoAvailableSlotsError

            next_slot = slot_manager.get_next_slot_number()
        except NoAvailableSlotsError as e:
            console.print(f"\n[red]✗[/red] {e.message}")
            console.print(f"[bold]💡 Solution:[/bold] {e.suggestion}\n")
            raise SystemExit(1) from e

        # Ask for slot number
        while True:
            slot_number = IntPrompt.ask(
                f"[cyan]Which slot would you like to configure?[/cyan] (next available: {next_slot})",
                default=next_slot,
            )

            if slot_number < 1:
                console.print("[red]✗[/red] Slot number must be 1 or greater\n")
                continue

            if slot_number in occupied_slots:
                console.print(f"[yellow]⚠[/yellow]  Slot {slot_number} is already occupied\n")
                retry = Confirm.ask("Choose a different slot?", default=True)
                if not retry:
                    console.print("\n[yellow]Cancelled[/yellow]\n")
                    raise SystemExit(0)
                continue

            break

        # Ask for AI provider using shared selection workflow
        ai_provider = _select_provider()

        # Show Gemini authentication hint
        if ai_provider == "gemini":
            from rich.panel import Panel

            console.print()
            console.print(
                Panel(
                    "[bold yellow]Gemini Authentication Recommendation[/bold yellow]\n\n"
                    "Gemini CLI authenticates with OAuth on a random local port.\n"
                    "When you configure a Gemini slot, a short-lived container will run\n"
                    "`gemini login` on the host network so the browser callback works.\n\n"
                    "You'll see a login URL in the terminal; complete the flow in your browser\n"
                    "and the session will be stored under this slot's `.gemini/` directory.\n"
                    "No API keys are used or required.",
                    border_style="yellow",
                    padding=(1, 2),
                )
            )
            console.print()

        # Create slot metadata without container (pre-configuration)
        console.print(f"\n[bold blue]Configuring slot {slot_number}...[/bold blue]\n")

        slot_config = slot_manager.get_slot(slot_number)
        # Save with empty container name (will be set when container is created)
        slot_config.save(
            ai_provider=ai_provider,
            container_name="",  # No container yet
        )

        # Trigger Gemini OAuth capture if needed
        if ai_provider == "gemini":
            _ensure_gemini_session(project_root, slot_number)
        elif ai_provider == "openai":
            _ensure_openai_session(project_root, slot_number)

        console.print(
            f"[bold green]✓[/bold green] Slot {slot_number} configured with {ai_provider}\n"
        )
        console.print(
            f"[dim]Run [cyan]aibox start --slot {slot_number}[/cyan] to start this slot[/dim]\n"
        )

    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠[/yellow]  Cancelled by user\n")
        raise SystemExit(130) from None
    except ConfigNotFoundError:
        raise
    except Exception as e:
        console.print(f"\n[red]✗[/red] Error: {e}\n")
        raise SystemExit(1) from e


def _stream_build_with_live(
    build_func: Callable[[Callable[[str], None]], None], status: str
) -> None:
    """
    Render build logs inside a fixed live region to avoid scrolling the whole terminal.
    """
    console.print(status)
    build_lines: list[str] = []

    with Live(console=console, auto_refresh=True, refresh_per_second=4) as live:

        def live_progress(line: str) -> None:
            clean = line.rstrip("\n")
            if not clean:
                return
            build_lines.append(clean)
            if len(build_lines) > 20:
                build_lines.pop(0)

            text = Text()
            for log_line in build_lines[-15:]:
                text.append(log_line + "\n", style="dim")

            live.update(text)

        build_func(live_progress)


def _ensure_gemini_session(project_root: Path, slot_number: int) -> None:
    """
    Run a short-lived Gemini login container (host network) if no session exists.
    """
    storage_dir = get_project_storage_dir(project_root)
    slot_dir = Path.home() / ".aibox" / "projects" / storage_dir / "slots" / f"slot-{slot_number}"
    gemini_dir = slot_dir / ".gemini"
    if gemini_dir.exists():
        try:
            if any(p.is_file() and p.stat().st_size > 0 for p in gemini_dir.iterdir()):
                return
        except OSError:
            pass

    console.print("[bold blue]Running Gemini login for this slot...[/bold blue]")

    provider = ProviderRegistry.get_provider("gemini")
    config = load_config(str(project_root))
    container_manager = ContainerManager()

    _stream_build_with_live(
        lambda progress_cb: _ensure_gemini_image(
            container_manager, config, provider, slot_number, progress_callback=progress_cb
        ),
        status="[bold cyan]Preparing Gemini helper image...[/bold cyan]",
    )

    volume_manager = VolumeManager(project_dir=project_root, project_storage_dir=storage_dir)
    volumes = volume_manager.prepare_volumes(
        slot_number=slot_number, provider=provider, custom_mounts=config.project.mounts
    )
    env_vars = provider.get_docker_env_vars()

    container = container_manager.create_container(
        image=f"aibox-{config.project.name}-gemini:latest",
        name=f"aibox-gemini-login-{slot_number}",
        volumes=volumes,
        environment=env_vars,
        command=["gemini", "login"],
        network_mode="host",
    )

    try:
        container_manager.start_container(container)
        with contextlib.suppress(Exception):
            for chunk in container.logs(stream=True, follow=True):
                try:
                    console.print(chunk.decode("utf-8", errors="ignore"), end="")
                except Exception:
                    continue

        result = container.wait()
        status_code = result.get("StatusCode") if isinstance(result, dict) else None
        if status_code not in (0, None):
            raise RuntimeError(f"Gemini login failed with status {status_code}")
    finally:
        with contextlib.suppress(Exception):
            container.remove(force=True)


def _ensure_openai_session(project_root: Path, slot_number: int) -> None:
    """
    Run a short-lived OpenAI (Codex) login container on the host network if no session exists.
    """
    storage_dir = get_project_storage_dir(project_root)
    provider = ProviderRegistry.get_provider("openai")

    # Skip if slot-scoped Codex session already exists
    if not provider.get_required_ports(project_storage_dir=storage_dir, slot_number=slot_number):
        return

    console.print("[bold blue]Running OpenAI login for this slot...[/bold blue]")

    config = load_config(str(project_root))
    container_manager = ContainerManager()

    _stream_build_with_live(
        lambda progress_cb: _ensure_provider_image(
            container_manager, config, provider, progress_callback=progress_cb
        ),
        status="[bold cyan]Preparing OpenAI helper image...[/bold cyan]",
    )

    volume_manager = VolumeManager(project_dir=project_root, project_storage_dir=storage_dir)
    volumes = volume_manager.prepare_volumes(
        slot_number=slot_number, provider=provider, custom_mounts=config.project.mounts
    )
    env_vars = provider.get_docker_env_vars()

    container = container_manager.create_container(
        image=f"aibox-{config.project.name}-openai:latest",
        name=f"aibox-openai-login-{slot_number}",
        volumes=volumes,
        environment=env_vars,
        command=["codex", "login"],
        network_mode="host",
    )

    try:
        container_manager.start_container(container)

        # Clear the screen so Codex CLI renders its full TTY output (logo, animations)
        sys.stdout.write("\033c")
        sys.stdout.flush()

        with contextlib.suppress(Exception):
            for chunk in container.logs(stream=True, follow=True):
                if not chunk:
                    continue
                try:
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.flush()
                except Exception:
                    # If writing raw bytes fails, fall back to best-effort decoding
                    try:
                        sys.stdout.write(chunk.decode("utf-8", errors="ignore"))
                        sys.stdout.flush()
                    except Exception:
                        continue

        result = container.wait()
        status_code = result.get("StatusCode") if isinstance(result, dict) else None
        if status_code not in (0, None):
            raise RuntimeError(f"OpenAI login failed with status {status_code}")
    finally:
        with contextlib.suppress(Exception):
            container.remove(force=True)


def _ensure_gemini_image(
    container_manager: ContainerManager,
    config: Config,
    provider: AIProvider,
    _slot_number: int,
    progress_callback: Callable[[str], None] | None = None,
) -> None:
    """Build gemini image if missing."""
    _ensure_provider_image(container_manager, config, provider, progress_callback=progress_callback)


def _ensure_provider_image(
    container_manager: ContainerManager,
    config: Config,
    provider: AIProvider,
    progress_callback: Callable[[str], None] | None = None,
) -> None:
    """Build provider image if missing."""
    image_tag_latest = f"aibox-{config.project.name}-{provider.name}:latest"
    if container_manager.image_exists(image_tag_latest):
        return

    profile_loader = ProfileLoader()
    profiles_with_versions = [
        profile_loader.load_profile(profile_spec) for profile_spec in config.project.profiles
    ]

    generator = DockerfileGenerator(base_image=config.global_config.docker.base_image)
    base_dockerfile = generator.generate(
        profiles_with_versions=profiles_with_versions,
        ai_provider=None,
    )
    base_build_args = generator.generate_build_args(profiles_with_versions)

    orchestrator = ContainerOrchestrator()
    base_hash = orchestrator._generate_base_image_hash(
        dockerfile_content=base_dockerfile,
        base_image=config.global_config.docker.base_image,
        profiles=config.project.profiles,
    )
    base_tag_hash = f"aibox-{config.project.name}-base:{base_hash}"
    base_tag_latest = f"aibox-{config.project.name}-base:latest"

    if not container_manager.image_exists(base_tag_hash):
        with TemporaryDirectory() as tmpdir:
            dockerfile_path = Path(tmpdir) / "Dockerfile"
            dockerfile_path.write_text(base_dockerfile)
            container_manager.build_image(
                dockerfile_path=tmpdir,
                tag=base_tag_hash,
                buildargs=base_build_args,
                progress_callback=progress_callback,
            )
        container_manager.tag_image(base_tag_hash, base_tag_latest)
    else:
        container_manager.tag_image(base_tag_hash, base_tag_latest)

    provider_dockerfile = generator.generate_provider_layer(
        base_tag=base_tag_hash, ai_provider=provider.name
    )
    provider_hash = orchestrator._generate_provider_image_hash(
        dockerfile_content=provider_dockerfile,
        provider_name=provider.name,
        base_hash=base_hash,
    )
    image_tag_hash = f"aibox-{config.project.name}-{provider.name}:{provider_hash}"

    if not container_manager.image_exists(image_tag_hash):
        with TemporaryDirectory() as tmpdir:
            dockerfile_path = Path(tmpdir) / "Dockerfile"
            dockerfile_path.write_text(provider_dockerfile)
            container_manager.build_image(
                dockerfile_path=tmpdir,
                tag=image_tag_hash,
                cache_from=[base_tag_hash, base_tag_latest],
                progress_callback=progress_callback,
            )
    container_manager.tag_image(image_tag_hash, image_tag_latest)
