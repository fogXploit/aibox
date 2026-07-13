"""
Interactive project initialization command with Rich UI.

This module provides the 'init' command which creates both global and project
configurations through an interactive wizard with beautiful terminal output.
"""

from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from aibox.config.loader import (
    create_default_global_config,
    get_global_config_path,
    load_global_config,
    save_aibox_ref,
    save_global_config,
    save_project_config,
)
from aibox.config.models import ProjectConfig
from aibox.profiles.loader import ProfileLoader
from aibox.utils.errors import AiboxError
from aibox.utils.hash import get_project_storage_dir

console = Console()


def init_command() -> None:
    """
    Initialize aibox project with interactive wizard.

    This command:
    1. Checks for/creates global config (~/.aibox/config.yml) on first run
    2. Verifies we're in a valid project directory
    3. Runs interactive wizard to configure project
    4. Creates .aibox/config.yml in current directory

    Example:
        >>> init_command()
        ✓ Global config found
        Creating project configuration...
        ✓ Project initialized!
    """
    try:
        # Display ASCII art banner
        ascii_art = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║             █████╗ ██╗  ██████╗  █████╗  ██╗  ██╗             ║
║            ██╔══██╗██║  ██╔══██╗██╔══██╗░╚██╗██╔╝             ║
║            ███████║██║  ██████╔╝██║░░██║░░╚███╔╝░             ║
║            ██╔══██║██║  ██╔══██╗██║░░██║░░██╔██╗░             ║
║            ██║░░██║██║  ██████╔╝╚█████╔╝ ██╔╝╚██╗             ║
║            ╚═╝░░╚═╝╚═╝  ╚═════╝░░╚════╝░ ╚═╝░░╚═╝             ║
║                                                               ║
║       Container-Based Multi-AI Development Environment        ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
        """
        console.print(ascii_art, style="cyan")
        console.print()

        # Step 1: Check/create global config
        global_config_path = get_global_config_path()

        if global_config_path.exists():
            console.print("✓ Global config found", style="green")
            load_global_config()  # Validate it's loadable
        else:
            console.print("\n[yellow]Creating global config (~/.aibox/config.yml)...[/yellow]\n")
            global_config = create_default_global_config()
            save_global_config(global_config)
            console.print("✓ Global config created", style="green")

        # Step 2: Verify we're in a valid project directory
        cwd = Path.cwd()
        if cwd == Path.home():
            raise AiboxError(
                "Cannot initialize aibox in home directory.\n"
                "Please cd to your project directory first."
            )
        if cwd == Path("/"):
            raise AiboxError(
                "Cannot initialize aibox in root directory.\n"
                "Please cd to your project directory first."
            )

        project_config_path = cwd / ".aibox" / "config.yml"
        if project_config_path.exists():
            overwrite = Confirm.ask(
                "\n[yellow]Project already initialized. Recreate config?[/yellow]", default=False
            )
            if not overwrite:
                console.print("\n[yellow]Aborted[/yellow]")
                return

        # Step 3: Show welcome message
        console.print(
            Panel(
                "[bold cyan]aiBox Project Initialization[/bold cyan]\n\n"
                "This wizard will help you configure aiBox for your project.",
                border_style="cyan",
            )
        )

        # Step 4: Interactive prompts

        # Project name
        default_name = cwd.name
        project_name = Prompt.ask("\n[cyan]Project name[/cyan]", default=default_name)

        # Profile selection (interactive multi-select)
        console.print()
        profile_loader = ProfileLoader()
        available_profiles = profile_loader.list_profiles_with_info()
        profiles_by_name = {info["name"]: info for info in available_profiles}

        selected_names: list[str] = []
        if available_profiles:
            profile_choices = [
                questionary.Choice(
                    title=f"{info['name']} — {info['description']} ({info['versions']})",
                    value=info["name"],
                )
                for info in available_profiles
            ]
            checkbox_answer = questionary.checkbox(
                "Select profiles (space to toggle, enter to confirm)",
                choices=profile_choices,
            ).ask()
            # ask() returns None on Ctrl+C/EOF - treat as "no profiles selected"
            if checkbox_answer is not None:
                selected_names = list(checkbox_answer)

        selected_profiles = []
        for profile_name in selected_names:
            info = profiles_by_name[profile_name]
            default_version = info["default_version"]
            version_choices = [
                questionary.Choice(title=f"default ({default_version})", value="")
            ]
            for available_version in info["versions_list"]:
                version_choices.append(
                    questionary.Choice(title=available_version, value=available_version)
                )
            # ask() returns None on Ctrl+C/EOF - treat as "use default"
            version = questionary.select(
                f"Version for {profile_name}",
                choices=version_choices,
            ).ask()
            if version:
                selected_profiles.append(f"{profile_name}:{version}")
            else:
                selected_profiles.append(profile_name)

        if not selected_profiles:
            console.print(
                "[yellow]No profiles selected. Container will use base Ubuntu image only.[/yellow]"
            )

        # Step 5: Create project config
        # Note: AI provider selection happens per-slot when starting containers
        project_config = ProjectConfig(
            name=project_name,
            profiles=selected_profiles,
        )

        # Get storage directory name
        storage_dir = get_project_storage_dir(cwd)

        # Save project config to ~/.aibox/projects/<hash>/config.yml
        save_project_config(project_config, cwd)

        # Create .aibox directory in project (for .aibox-ref file)
        config_dir = cwd / ".aibox"
        config_dir.mkdir(exist_ok=True)

        # Save .aibox-ref file
        save_aibox_ref(cwd, storage_dir)

        # Step 6: Success message
        console.print(
            Panel(
                "[bold green]✓ Project initialized![/bold green]\n\n"
                "[bold]Next steps:[/bold]\n"
                "  1. Review config: [cyan]aibox config show[/cyan]\n"
                "  2. Start container: [cyan]aibox start[/cyan] (select AI provider interactively)\n"
                "  3. Add more slots: [cyan]aibox slot add[/cyan]",
                border_style="green",
                title="Success",
            )
        )

    except AiboxError:
        # Re-raise aibox errors to be handled by main error handler
        raise
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Aborted by user[/yellow]")
        raise SystemExit(130) from None
    except Exception as e:
        # Wrap unexpected errors
        raise AiboxError(f"Initialization failed: {e}") from e
