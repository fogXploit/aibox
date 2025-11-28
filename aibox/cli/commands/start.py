"""
Start command implementation with Rich output.

This module provides the 'start' command which starts an aibox container.
The command uses ContainerOrchestrator for business logic and focuses on
user interaction with beautiful Rich terminal output.
"""

import time
import typing as t
from collections.abc import Callable
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt
from rich.table import Table
from rich.text import Text

from aibox.config.loader import load_project_config
from aibox.containers.orchestrator import ContainerOrchestrator
from aibox.containers.slot import SlotManager
from aibox.providers.registry import ProviderRegistry
from aibox.utils.errors import ConfigNotFoundError
from aibox.utils.hash import get_project_storage_dir

console = Console()


def _select_provider() -> str:
    """Render provider list and return the selected provider name."""
    provider_names = ProviderRegistry.list_providers()
    providers = [ProviderRegistry.get_provider(name) for name in provider_names]

    console.print("\n[bold]Available AI Providers:[/bold]")
    for idx, provider in enumerate(providers, start=1):
        console.print(f"  {idx}. [cyan]{provider.name}[/cyan] - {provider.display_name}")
    console.print()

    provider_choice = IntPrompt.ask(
        "[cyan]AI provider?[/cyan]",
        choices=[str(i) for i in range(1, len(providers) + 1)],
        default=1,
    )

    chosen_provider = providers[provider_choice - 1].name
    return chosen_provider


def _slot_wizard(project_root: Path) -> tuple[int, str | None]:
    """
    Interactive wizard to select or configure a slot.

    Returns:
        Tuple of (slot_number, ai_provider) where ai_provider is None if using pre-configured slot

    Raises:
        SystemExit: If user cancels
    """
    storage_dir = get_project_storage_dir(project_root)
    slot_manager = SlotManager(storage_dir)

    # Get pre-configured slots
    slots_list = slot_manager.list_slots()
    preconfigured_slots = {
        slot["slot"]: slot["ai_provider"] for slot in slots_list if slot.get("ai_provider")
    }

    console.print("\n[bold blue]Select Slot[/bold blue]\n")

    # Show pre-configured slots if any exist
    if preconfigured_slots:
        console.print("[bold]Pre-configured slots:[/bold]")
        for slot_num in sorted(preconfigured_slots.keys()):
            provider = preconfigured_slots[slot_num]
            console.print(f"  • Slot {slot_num}: [cyan]{provider}[/cyan]")
        console.print()

        # Ask if user wants to use a pre-configured slot
        use_existing = Confirm.ask("Use a pre-configured slot?", default=True)

        if use_existing:
            while True:
                slot_choice = IntPrompt.ask(
                    "[cyan]Which slot?[/cyan]",
                    choices=[str(s) for s in sorted(preconfigured_slots.keys())],
                )
                if slot_choice in preconfigured_slots:
                    return (slot_choice, None)  # Use pre-configured provider
                console.print(f"[red]✗[/red] Slot {slot_choice} is not pre-configured\n")

    # Configure new slot
    console.print("\n[bold]Configure new slot:[/bold]")

    # Get occupied slots
    occupied_slots = {slot["slot"] for slot in slots_list}
    if occupied_slots:
        console.print(f"[dim]Occupied: {', '.join(map(str, sorted(occupied_slots)))}[/dim]\n")

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
            f"[cyan]Slot number?[/cyan] (next available: {next_slot})",
            default=next_slot,
        )

        if slot_number < 1:
            console.print("[red]✗[/red] Slot must be 1 or greater\n")
            continue

        if slot_number in occupied_slots:
            console.print(f"[yellow]⚠[/yellow]  Slot {slot_number} is already occupied\n")
            retry = Confirm.ask("Choose different slot?", default=True)
            if retry:
                continue
            else:
                console.print("\n[yellow]Cancelled[/yellow]\n")
                raise SystemExit(0)

        break

    ai_provider = _select_provider()

    # Show Gemini authentication hint
    if ai_provider == "gemini":
        console.print()
        console.print(
            Panel(
                "[bold yellow]Gemini Authentication Recommendation[/bold yellow]\n\n"
                "Gemini CLI authenticates with OAuth on a random local port.\n"
                "When you configure a Gemini slot, a short-lived container will run\n"
                "`gemini login` on the host network so the browser callback works.\n\n"
                "You'll see a login URL in the terminal; complete the flow in your browser\n"
                "and the session will be stored under this slot's .gemini/ directory.\n"
                "No API keys are used or required.",
                border_style="yellow",
                padding=(1, 2),
            )
        )
        console.print()

    return (slot_number, ai_provider)


def _run_with_live_progress(status: str, runner: Callable[[Callable[[str], None]], t.Any]) -> t.Any:
    """
    Execute a callable while rendering its progress logs inside a fixed Live region.
    """
    console.print(f"[bold cyan]{status}[/bold cyan]\n")

    build_lines: list[str] = []

    with Live(console=console, auto_refresh=True, refresh_per_second=4) as live:

        def live_progress(line: str) -> None:
            clean = line.rstrip("\n")
            if not clean:
                return
            build_lines.append(clean)
            if len(build_lines) > 20:
                build_lines.pop(0)

            output_text = Text()
            for log_line in build_lines[-15:]:
                output_text.append(log_line + "\n", style="dim")
            live.update(output_text)

        return runner(live_progress)


def start_command(
    project_root: Path,
    slot_number: int | None = None,
    force_openai_auth_port: bool = False,
    auto_delete: bool = False,
    resume: bool = False,
) -> None:
    """
    Start aibox container for the project.

    This command provides a beautiful CLI experience with:
    - Colored output for different message types
    - Spinners for long-running operations
    - Success indicators and container information
    - Helpful error messages

    Args:
        project_root: Project root directory
        slot_number: Slot number (auto-assigns next available if None)

    Example:
        >>> start_command(
        ...     project_root=Path.cwd(),
        ...     slot_number=1
        ... )
        ✓ Container started successfully!
    """
    try:
        # Check if project is initialized
        try:
            load_project_config(str(project_root))
        except ConfigNotFoundError:
            console.print("\n[yellow]⚠[/yellow]  Project not initialized\n")
            console.print("This directory has not been initialized as an aibox project.\n")

            # Ask if user wants to run init
            should_init = Confirm.ask(
                "Would you like to initialize this project now?", default=True
            )

            if should_init:
                console.print("\n[bold blue]Initializing project...[/bold blue]\n")
                # Import here to avoid circular dependency
                import os

                from aibox.cli.commands.init import init_command

                try:
                    # Change to project directory temporarily
                    original_dir = Path.cwd()
                    os.chdir(project_root)
                    try:
                        init_command()
                        console.print("\n[bold green]✓[/bold green] Project initialized!\n")
                    finally:
                        os.chdir(original_dir)
                except Exception as e:
                    console.print(f"\n[red]✗[/red] Initialization failed: {e}\n")
                    raise SystemExit(1) from e
            else:
                console.print("\n[yellow]Cancelled[/yellow]\n")
                console.print("Run [cyan]aibox init[/cyan] to initialize the project first.\n")
                raise SystemExit(0) from None

        storage_dir = get_project_storage_dir(project_root)
        slot_manager: SlotManager | None = None

        # If no slot specified, run interactive wizard
        if slot_number is None:
            slot_number, ai_provider = _slot_wizard(project_root)
        else:
            # Validate that specified slot exists and is pre-configured
            slot_manager = SlotManager(storage_dir)
            slot_config = slot_manager.get_slot(slot_number)

            if not slot_config.exists():
                console.print(f"\n[yellow]⚠[/yellow]  Slot {slot_number} is not configured\n")
                configure = Confirm.ask(f"Configure slot {slot_number} now?", default=True)

                if configure:
                    # Get available providers
                    ai_provider = _select_provider()
                else:
                    console.print("\n[yellow]Cancelled[/yellow]\n")
                    raise SystemExit(0)
            else:
                # Slot exists, use None to signal orchestrator to read from slot config
                ai_provider = None

        resolved_ai_provider = ai_provider
        if resolved_ai_provider is None:
            slot_manager = slot_manager or SlotManager(storage_dir)
            slot_config = slot_manager.get_slot(slot_number)
            slot_data = slot_config.load()
            resolved_ai_provider = slot_data.get("ai_provider") if slot_data else None

        if resolved_ai_provider == "openai":
            from aibox.cli.commands.slot import _ensure_openai_session

            _ensure_openai_session(project_root, slot_number)

        # Show starting message
        console.print("\n[bold blue]Starting aibox container...[/bold blue]\n")

        # Create orchestrator and start container with live progress
        orchestrator = ContainerOrchestrator()

        # Track progress
        build_start_time = time.time()

        try:
            container_info = _run_with_live_progress(
                "Building Docker image...",
                lambda progress_cb: orchestrator.start_container(
                    project_root=project_root,
                    slot_number=slot_number,
                    ai_provider=ai_provider,
                    force_openai_auth_port=force_openai_auth_port,
                    reuse_existing=True,
                    auto_remove=auto_delete,
                    progress_callback=progress_cb,
                ),
            )

            # Show build completion
            build_elapsed = time.time() - build_start_time
            console.print(f"[bold green]✓[/bold green] Docker image built ({build_elapsed:.1f}s)\n")

            # Show container starting
            container_start_time = time.time()
            console.print("[bold cyan]● Starting container...[/bold cyan]")
            container_elapsed = time.time() - container_start_time
            console.print(
                f"[bold green]✓[/bold green] Container started ({container_elapsed:.1f}s)\n"
            )

        except Exception:
            # If build fails, show error and re-raise
            build_elapsed = time.time() - build_start_time
            console.print(f"\n[bold red]✗[/bold red] Build failed after {build_elapsed:.1f}s\n")
            raise

        # Show success message with container details
        console.print("\n[bold green]✓[/bold green] Container started successfully!\n")

        # Create info table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Container ID", container_info.container_id[:12])
        table.add_row("Container Name", container_info.container_name)
        table.add_row("Slot", str(container_info.slot_number))
        table.add_row("AI Provider", container_info.ai_provider)
        table.add_row("Project", container_info.project_name)

        # Show table in panel
        panel = Panel(
            table,
            title="[bold]Container Information[/bold]",
            border_style="green",
        )
        console.print(panel)

        # Auto-attach to AI CLI
        console.print(
            f"\n[bold cyan]Connecting to {container_info.ai_provider} CLI...[/bold cyan]\n"
        )

        exit_code = 0
        try:
            console.clear()
            exit_code = orchestrator.attach_to_container(
                project_root=project_root,
                slot_number=container_info.slot_number,
                resume=resume,
            )
        finally:
            console.print(f"\n[dim]Exited {container_info.ai_provider} CLI[/dim]")

            with console.status(
                "[bold cyan]Stopping container...[/bold cyan]",
                spinner="dots",
            ):
                try:
                    orchestrator.stop_container(
                        project_root=project_root,
                        slot_number=container_info.slot_number,
                    )
                    if auto_delete:
                        console.print(
                            "[bold green]✓[/bold green] Container stopped (auto-delete enabled; Docker will remove it)\n"
                        )
                    else:
                        console.print(
                            "[bold green]✓[/bold green] Container stopped and preserved for continuation\n"
                        )
                except Exception as e:
                    console.print(f"[yellow]⚠[/yellow]  Warning: Failed to stop container: {e}\n")

        # Exit with same code as AI CLI session
        raise SystemExit(exit_code)

    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠[/yellow]  Cancelled by user")
        # Try to clean up container if it was created
        try:
            if "container_info" in locals():
                with console.status(
                    "[bold cyan]Cleaning up...[/bold cyan]",
                    spinner="dots",
                ):
                    orchestrator.stop_container(
                        project_root=project_root,
                        slot_number=container_info.slot_number,
                    )
                console.print("[bold green]✓[/bold green] Container cleaned up\n")
        except Exception:
            # Ignore cleanup errors on interrupt
            pass
        raise SystemExit(1) from None
    except Exception:
        # Error handling (errors are propagated to main CLI handler)
        raise
