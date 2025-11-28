"""
Configuration management commands.

Provides commands to view and validate aibox configuration.
"""

import os
import subprocess
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax

from aibox.config.loader import get_project_config_path, load_config
from aibox.containers.slot import SlotManager
from aibox.utils.errors import ConfigNotFoundError, SlotNotFoundError
from aibox.utils.hash import get_project_storage_dir

console = Console()


def config_show(project_root: Path, slot_number: int = 1) -> None:
    """
    Show current configuration.

    Displays the merged global + project + slot configuration in YAML format.

    Args:
        project_root: Project root directory
        slot_number: Slot number to show configuration for (default: 1)

    Raises:
        ConfigNotFoundError: If project configuration not found
        SlotNotFoundError: If specified slot doesn't exist
    """
    try:
        config = load_config(str(project_root))

        # Build global config dict
        config_dict = {
            "global": {
                "version": config.global_config.version,
                "docker": {
                    "base_image": config.global_config.docker.base_image,
                    "default_resources": {
                        "cpus": config.global_config.docker.default_resources.cpus,
                        "memory": config.global_config.docker.default_resources.memory,
                    },
                },
            },
            "project": {
                "name": config.project.name,
                "profiles": config.project.profiles,
                "mounts": [
                    {"source": m.source, "target": m.target, "mode": m.mode}
                    for m in config.project.mounts
                ],
                "environment": config.project.environment,
            },
        }

        # Load slot configuration
        storage_dir = get_project_storage_dir(project_root)
        slot_manager = SlotManager(storage_dir)
        slot_config = slot_manager.get_slot(slot_number)
        slot_data = slot_config.load()

        if slot_data is None:
            raise SlotNotFoundError(
                message=f"Slot {slot_number} not found",
                suggestion="Available slots: Use 'aibox slot list' to see configured slots, or create a new slot with 'aibox slot add'",
            )

        # Add slot config to dict
        config_dict["slot"] = {
            "slot_number": slot_number,
            **slot_data,
        }

        # Convert to YAML
        yaml_content = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)

        # Syntax highlighting
        syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=False)

        # Show in panel with slot number
        panel = Panel(
            syntax,
            title=f"[bold]aibox Configuration (Slot {slot_number})[/bold]",
            border_style="blue",
        )

        console.print()
        console.print(panel)
        console.print()

    except (ConfigNotFoundError, SlotNotFoundError):
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


def config_validate(project_root: Path) -> None:
    """
    Validate configuration files.

    Checks that configuration files are valid and can be loaded.

    Args:
        project_root: Project root directory
    """
    try:
        console.print("\n[bold blue]Validating configuration...[/bold blue]\n")

        with console.status("[cyan]Loading configuration...[/cyan]", spinner="dots"):
            config = load_config(str(project_root))

        # If we got here, config is valid
        console.print("[bold green]✓[/bold green] Configuration is valid!\n")

        # Show summary
        console.print("[bold]Summary:[/bold]")
        console.print(f"  • Project: [cyan]{config.project.name}[/cyan]")
        console.print(f"  • Profiles: [cyan]{len(config.project.profiles)}[/cyan]")
        console.print(f"  • Custom Mounts: [cyan]{len(config.project.mounts)}[/cyan]")
        console.print()

    except Exception as e:
        console.print("\n[bold red]✗[/bold red] Configuration is invalid\n")
        console.print(f"[red]Error:[/red] {e}\n")
        raise SystemExit(1) from e


def config_edit(project_root: Path) -> None:
    """
    Edit project configuration in your default editor.

    Opens the project config file from ~/.aibox/projects/<hash>/config.yml
    in the editor specified by $EDITOR or $VISUAL environment variable.
    After editing, validates the configuration and prompts to re-edit if invalid.

    Args:
        project_root: Project root directory

    Raises:
        ConfigNotFoundError: If project is not initialized
        SystemExit: If user aborts or validation fails
    """
    try:
        # Get project config path from centralized storage
        config_path = get_project_config_path(project_root)
        if not config_path.exists():
            raise ConfigNotFoundError(
                "No project configuration found",
                suggestion="Run 'aibox init' to initialize this project first",
            )

        # Get editor from environment
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "nano"

        console.print(f"\n[bold blue]Opening config in {editor}...[/bold blue]\n")

        # Open editor in a loop to allow re-editing on validation failure
        while True:
            # Open the config file in the editor
            try:
                result = subprocess.run([editor, str(config_path)], check=False)
                if result.returncode != 0:
                    console.print(
                        f"\n[yellow]Editor exited with code {result.returncode}[/yellow]\n"
                    )
            except FileNotFoundError:
                console.print(f"\n[red]Error:[/red] Editor '{editor}' not found\n")
                console.print(
                    "Set $EDITOR or $VISUAL environment variable to your preferred editor\n"
                )
                raise SystemExit(1) from None
            except Exception as e:
                console.print(f"\n[red]Error:[/red] Failed to open editor: {e}\n")
                raise SystemExit(1) from e

            # Validate the edited configuration
            console.print("\n[bold blue]Validating configuration...[/bold blue]\n")

            try:
                with console.status("[cyan]Loading configuration...[/cyan]", spinner="dots"):
                    config = load_config(str(project_root))

                # Configuration is valid
                console.print("[bold green]✓[/bold green] Configuration is valid!\n")

                # Show summary
                console.print("[bold]Updated configuration:[/bold]")
                console.print(f"  • Project: [cyan]{config.project.name}[/cyan]")
                console.print(
                    f"  • Profiles: [cyan]{', '.join(config.project.profiles) if config.project.profiles else 'none'}[/cyan]"
                )
                console.print()

                break  # Exit the loop, config is valid

            except Exception as e:
                # Configuration is invalid
                console.print("[bold red]✗[/bold red] Configuration is invalid\n")
                console.print(f"[red]Error:[/red] {e}\n")

                # Ask if user wants to re-edit
                retry = Confirm.ask(
                    "[yellow]Would you like to edit the configuration again?[/yellow]",
                    default=True,
                )

                if not retry:
                    console.print("\n[yellow]Aborted[/yellow]\n")
                    raise SystemExit(1) from e

                # Loop continues to re-edit

    except ConfigNotFoundError:
        # Re-raise to be handled by main error handler
        raise
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Aborted by user[/yellow]\n")
        raise SystemExit(130) from None
