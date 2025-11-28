"""
Profile management commands.

Provides commands to list and view information about available profiles.
"""

from rich.console import Console
from rich.table import Table

from aibox.profiles.loader import ProfileLoader

console = Console()


def profile_list() -> None:
    """
    List all available profiles.

    Shows a table with profile names, versions, and descriptions.
    """
    try:
        loader = ProfileLoader()
        all_profiles = loader.list_profiles()

        if not all_profiles:
            console.print("[yellow]No profiles found[/yellow]")
            return

        # Create table
        table = Table(title="[bold]Available Profiles[/bold]", show_lines=True)
        table.add_column("Profile", style="cyan", no_wrap=True)
        table.add_column("Versions", style="green")
        table.add_column("Description", style="white")

        for profile_name in sorted(all_profiles):
            profile, _ = loader.load_profile(profile_name)
            versions = ", ".join(profile.versions) if profile.versions else "N/A"
            table.add_row(
                profile_name,
                versions,
                profile.description or "No description",
            )

        console.print()
        console.print(table)
        console.print(f"\n[dim]Total: {len(all_profiles)} profiles[/dim]\n")
        console.print("[bold]Usage:[/bold] aibox start --profiles python:3.12,nodejs:20\n")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


def profile_info(profile_spec: str) -> None:
    """
    Show detailed information about a profile.

    Args:
        profile_spec: Profile specification (e.g., "python" or "python:3.12")
    """
    try:
        loader = ProfileLoader()

        # Parse profile spec
        if ":" in profile_spec:
            profile_name, _ = profile_spec.split(":", 1)
        else:
            profile_name = profile_spec

        profile, _ = loader.load_profile(profile_name)

        # Show profile information
        console.print(f"\n[bold cyan]{profile.name}[/bold cyan]\n")

        console.print(f"[bold]Description:[/bold] {profile.description or 'N/A'}")
        console.print(f"[bold]Package Manager:[/bold] {profile.package_manager or 'N/A'}")

        # Versions
        if profile.versions:
            console.print("\n[bold]Available Versions:[/bold]")
            for v in profile.versions:
                marker = "→" if v == profile.default_version else " "
                console.print(f"  {marker} {v}")

        # System dependencies
        if profile.system_dependencies:
            console.print("\n[bold]System Dependencies:[/bold]")
            for dep in profile.system_dependencies:
                console.print(f"  • {dep}")

        # Install commands
        if profile.install_commands:
            console.print("\n[bold]Install Commands:[/bold]")
            for cmd in profile.install_commands:
                console.print(f"  $ {cmd}")

        console.print()

    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Profile '{profile_spec}' not found")
        console.print("\nRun [cyan]aibox profile list[/cyan] to see available profiles\n")
        raise SystemExit(1) from None
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise
