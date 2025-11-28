"""Main CLI entry point for aibox with comprehensive error handling."""

import contextlib
from pathlib import Path

import typer
from rich.console import Console

from aibox import __version__
from aibox.cli.autocomplete import complete_profile_name, complete_slot_number
from aibox.cli.commands import (
    config_edit,
    config_show,
    config_validate,
    images_list,
    images_prune,
    init_command,
    profile_info,
    profile_list,
    slot_add,
    slot_cleanup,
    slot_list,
    start_command,
    status_command,
)
from aibox.utils.errors import (
    AiboxError,
    APIKeyNotFoundError,
    ConfigNotFoundError,
    DockerNotFoundError,
    NoAvailableSlotsError,
    ProviderNotFoundError,
    SlotNotFoundError,
)

app = typer.Typer(
    name="aibox",
    help="Container-Based Multi-AI Development Environment",
    no_args_is_help=True,
    add_completion=True,
)
console = Console()


# Init command
@app.command()
def init() -> None:
    """
    Initialize aibox project with interactive wizard.

    Creates .aibox/config.yml in the current directory through an
    interactive setup wizard. Also creates global config on first run.

    Examples:

      cd my-project && aibox init     # Initialize project interactively
    """
    try:
        init_command()
    except AiboxError as e:
        _handle_aibox_error(e)
    except SystemExit:
        raise  # Allow SystemExit (e.g., from Ctrl+C) to propagate
    except Exception as e:
        _handle_unexpected_error(e)


# Start command
@app.command()
def start(
    slot: int | None = typer.Option(
        None,
        "--slot",
        help="Slot number (1-10)",
        autocompletion=complete_slot_number,
    ),
    openai_auth_port: bool = typer.Option(
        False,
        "--openai-auth-port",
        help="Force exposing OpenAI OAuth port (use when reauthenticating Codex)",
    ),
    auto_delete: bool = typer.Option(
        False,
        "--auto-delete",
        help="Stop and remove the container after exiting the AI CLI (one-off session)",
    ),
    resume: bool = typer.Option(
        False,
        "--resume",
        help="Start Codex with 'resume' when a session exists for this slot",
    ),
) -> None:
    """
    Start aibox container for current project.

    Examples:

      aibox start                      # Interactive wizard (select slot + AI provider)

      aibox start --slot 2             # Use slot 2 (must be pre-configured)
    """
    try:
        start_command(
            project_root=Path.cwd(),
            slot_number=slot,
            force_openai_auth_port=openai_auth_port,
            auto_delete=auto_delete,
            resume=resume,
        )
    except AiboxError as e:
        _handle_aibox_error(e)
    except Exception as e:
        _handle_unexpected_error(e)


@app.command()
def status() -> None:
    """Show project configuration summary and slot status."""
    try:
        status_command(project_root=Path.cwd())
    except AiboxError as e:
        _handle_aibox_error(e)
    except Exception as e:
        _handle_unexpected_error(e)


# Profile commands
profile_app = typer.Typer(help="Manage profiles")
app.add_typer(profile_app, name="profile")


@profile_app.command("list")
def profile_list_cmd() -> None:
    """List all available profiles."""
    try:
        profile_list()
    except Exception as e:
        _handle_unexpected_error(e)


@profile_app.command("info")
def profile_info_cmd(
    profile: str = typer.Argument(
        ...,
        help="Profile name (e.g., python or python:3.12)",
        autocompletion=complete_profile_name,
    ),
) -> None:
    """Show detailed information about a profile."""
    try:
        profile_info(profile)
    except Exception as e:
        _handle_unexpected_error(e)


# Slot commands
slot_app = typer.Typer(help="Manage container slots")
app.add_typer(slot_app, name="slot")


@slot_app.command("list")
def slot_list_cmd() -> None:
    """List all container slots."""
    try:
        slot_list(project_root=Path.cwd())
    except Exception as e:
        _handle_unexpected_error(e)


@slot_app.command("add")
def slot_add_cmd() -> None:
    """Configure a new slot with interactive wizard."""
    try:
        slot_add(project_root=Path.cwd())
    except Exception as e:
        _handle_unexpected_error(e)


@slot_app.command("cleanup")
def slot_cleanup_cmd(
    slot: int | None = typer.Option(
        None,
        "--slot",
        help="Slot number to clean up (1-10). If not provided, cleans all slots.",
        autocompletion=complete_slot_number,
    ),
) -> None:
    """
    Clean up stopped container slots.

    Examples:

      aibox slot cleanup              # Clean up all stopped slots

      aibox slot cleanup --slot 2     # Clean up only slot 2
    """
    try:
        slot_cleanup(project_root=Path.cwd(), slot_number=slot)
    except Exception as e:
        _handle_unexpected_error(e)


# Config commands
config_app = typer.Typer(help="Manage configuration")
app.add_typer(config_app, name="config")


# Image commands
images_app = typer.Typer(help="Manage Docker images")
app.add_typer(images_app, name="images")


@images_app.command("list")
def images_list_cmd() -> None:
    """List all aibox Docker images for the current project."""
    try:
        images_list(project_root=Path.cwd())
    except Exception as e:
        _handle_unexpected_error(e)


@images_app.command("prune")
def images_prune_cmd(
    all_projects: bool = typer.Option(
        False,
        "--all",
        help="Prune dangling images for all projects (not just current project)",
    ),
) -> None:
    """
    Remove dangling Docker images (images with <none> tag).

    Examples:

      aibox images prune             # Prune dangling images

      aibox images prune --all       # Prune all dangling aibox images
    """
    try:
        # If --all is specified, pass None for project_root
        project_root = None if all_projects else Path.cwd()
        images_prune(project_root=project_root, all_projects=all_projects)
    except Exception as e:
        _handle_unexpected_error(e)


@config_app.command("show")
def config_show_cmd(
    slot: int = typer.Option(
        1,
        "--slot",
        help="Slot number to show configuration for (default: 1)",
        autocompletion=complete_slot_number,
    ),
) -> None:
    """Show current configuration including slot-specific settings."""
    try:
        config_show(project_root=Path.cwd(), slot_number=slot)
    except ConfigNotFoundError as e:
        console.print(f"\n[red]✗[/red] {e.message}\n")
        if e.suggestion:
            console.print(f"[bold]💡 Solution:[/bold] {e.suggestion}\n")
        raise typer.Exit(1) from e
    except SlotNotFoundError as e:
        console.print(f"\n[red]✗[/red] {e.message}\n")
        if e.suggestion:
            console.print(f"[bold]💡 Solution:[/bold] {e.suggestion}\n")
        raise typer.Exit(1) from e
    except Exception as e:
        _handle_unexpected_error(e)


@config_app.command("validate")
def config_validate_cmd() -> None:
    """Validate configuration files."""
    # Error handling is done in the command itself
    with contextlib.suppress(Exception):
        config_validate(project_root=Path.cwd())


@config_app.command("edit")
def config_edit_cmd() -> None:
    """Edit project configuration in your default editor."""
    try:
        config_edit(project_root=Path.cwd())
    except ConfigNotFoundError as e:
        console.print(f"\n[red]✗[/red] {e.message}\n")
        if e.suggestion:
            console.print(f"[bold]💡 Solution:[/bold] {e.suggestion}\n")
        raise typer.Exit(1) from e
    except Exception as e:
        _handle_unexpected_error(e)


# Version callback
def version_callback(show_version: bool) -> None:
    """Show version and exit."""
    if show_version:
        console.print(f"aibox v{__version__}")
        raise typer.Exit()


# Main callback
@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """aibox - Multi-AI development environment."""


# Error handlers
def _handle_aibox_error(error: AiboxError) -> None:
    """Handle AiboxError with formatted output."""
    console.print(f"\n[red]❌ Error:[/red] {error.message}\n")

    if error.suggestion:
        console.print("[bold]💡 Solution:[/bold]")
        console.print(f"   {error.suggestion}\n")

    if error.doc_link:
        console.print("[bold]📚 Documentation:[/bold]")
        console.print(f"   {error.doc_link}\n")

    # Specific error handling
    if isinstance(error, ConfigNotFoundError):
        console.print("[dim]Run [cyan]aibox init[/cyan] to create configuration[/dim]\n")
    elif isinstance(error, ProviderNotFoundError):
        console.print("[dim]Run [cyan]aibox profile list[/cyan] to see available profiles[/dim]\n")
    elif isinstance(error, APIKeyNotFoundError):
        console.print("[dim]Check your environment variables[/dim]\n")
    elif isinstance(error, DockerNotFoundError):
        console.print("[dim]Make sure Docker is installed and running[/dim]\n")
    elif isinstance(error, NoAvailableSlotsError):
        console.print("[dim]Run [cyan]aibox slot list[/cyan] to see active slots[/dim]\n")
        console.print("[dim]Containers auto-stop when you exit the AI CLI[/dim]\n")

    raise typer.Exit(1)


def _handle_unexpected_error(error: Exception) -> None:
    """Handle unexpected errors."""
    console.print(f"\n[red]❌ Unexpected Error:[/red] {error}\n")
    console.print("[dim]This might be a bug. Please report it at:")
    console.print("https://github.com/fogXploit/aibox/issues[/dim]\n")
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
