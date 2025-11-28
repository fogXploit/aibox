"""
Image management commands.

Provides commands to list and prune Docker images created by aibox.
"""

from pathlib import Path

from rich.console import Console
from rich.table import Table

from aibox.containers.manager import ContainerManager
from aibox.utils.errors import DockerNotFoundError
from aibox.utils.hash import get_project_storage_dir

console = Console()


def images_list(project_root: Path) -> None:
    """
    List all aibox Docker images for the current project.

    Shows a table with image tags, sizes, and creation dates.

    Args:
        project_root: Project root directory
    """
    try:
        # Initialize container manager
        try:
            container_manager = ContainerManager()
        except DockerNotFoundError as e:
            console.print(f"\n[red]✗[/red] {e.message}\n")
            console.print(f"[bold]💡 Solution:[/bold] {e.suggestion}\n")
            return

        # Get project name from storage directory
        storage_dir = get_project_storage_dir(project_root)
        storage_dir_name = Path(storage_dir).name
        project_name = storage_dir_name.rsplit("-", 1)[0] if "-" in storage_dir_name else "aibox"

        # List images with project name filter
        filters = {"reference": f"aibox-{project_name}-*"}
        images = container_manager.list_images(filters=filters)

        if not images:
            console.print(
                f"\n[yellow]No aibox images found for project '{project_name}'[/yellow]\n"
            )
            console.print(
                "[dim]Images are created automatically when you run 'aibox start'[/dim]\n"
            )
            return

        # Create table
        table = Table(title=f"[bold]aibox Images - {project_name}[/bold]", show_lines=False)
        table.add_column("Tag", style="cyan", no_wrap=True)
        table.add_column("Image ID", style="dim", no_wrap=True)
        table.add_column("Size", style="green", justify="right")
        table.add_column("Created", style="yellow")

        total_size = 0
        for image in images:
            # Get all tags for this image
            tags = image.tags if image.tags else ["<none>:<none>"]

            # Get image details
            image_id = image.short_id.replace("sha256:", "")
            size_bytes = image.attrs.get("Size", 0)
            size_mb = size_bytes / (1024 * 1024)
            total_size += size_bytes

            # Get created date
            created = image.attrs.get("Created", "N/A")
            if created != "N/A":
                # Parse and format date
                from datetime import datetime

                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    created = created_dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass

            # Add row for each tag
            for tag in tags:
                # Highlight hash tags vs :latest
                tag_display = f"[bold]{tag}[/bold]" if ":latest" in tag else tag

                table.add_row(
                    tag_display,
                    image_id,
                    f"{size_mb:.1f} MB",
                    created,
                )

        console.print()
        console.print(table)

        # Show summary
        total_size_mb = total_size / (1024 * 1024)
        console.print(
            f"\n[dim]Total images: {len(images)} | Total size: {total_size_mb:.1f} MB[/dim]\n"
        )

        # Show hint about cleanup
        console.print("[dim]💡 Run [cyan]aibox images prune[/cyan] to remove unused images[/dim]\n")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


def images_prune(project_root: Path | None = None, all_projects: bool = False) -> None:
    """
    Prune dangling aibox Docker images.

    Removes images with <none> tags that are no longer needed.

    Args:
        project_root: Project root directory (optional for project-specific pruning)
        all_projects: If True, prune dangling images for all aibox projects
    """
    try:
        # Initialize container manager
        try:
            container_manager = ContainerManager()
        except DockerNotFoundError as e:
            console.print(f"\n[red]✗[/red] {e.message}\n")
            console.print(f"[bold]💡 Solution:[/bold] {e.suggestion}\n")
            return

        # Determine scope
        if all_projects or project_root is None:
            console.print("\n[bold blue]Pruning dangling aibox images...[/bold blue]\n")
            filters = None  # Prune all dangling images
        else:
            # Get project name for filtering
            storage_dir = get_project_storage_dir(project_root)
            storage_dir_name = Path(storage_dir).name
            project_name = (
                storage_dir_name.rsplit("-", 1)[0] if "-" in storage_dir_name else "aibox"
            )
            console.print(
                f"\n[bold blue]Pruning dangling images for project '{project_name}'...[/bold blue]\n"
            )
            filters = None  # Docker doesn't support reference filter for prune

        # Prune images
        with console.status(
            "[cyan]Removing dangling images...[/cyan]",
            spinner="dots",
        ):
            result = container_manager.prune_dangling_images(filters=filters)

        images_deleted = result.get("ImagesDeleted") or []
        space_reclaimed = result.get("SpaceReclaimed", 0)
        space_mb = space_reclaimed / (1024 * 1024)

        if images_deleted:
            console.print(
                f"[bold green]✓[/bold green] Removed {len(images_deleted)} dangling image(s)\n"
            )
            console.print(f"[dim]Space reclaimed: {space_mb:.1f} MB[/dim]\n")
        else:
            console.print("[green]✓[/green] No dangling images to remove\n")

    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠[/yellow]  Cancelled by user\n")
        raise SystemExit(1) from None
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise
