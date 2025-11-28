"""
Status command implementation.

Shows project configuration summary and current slot/container status.
"""

from pathlib import Path

from rich.console import Console
from rich.table import Table

from aibox.config.loader import load_config
from aibox.containers.manager import ContainerManager
from aibox.containers.slot import SlotManager
from aibox.utils.errors import DockerNotFoundError
from aibox.utils.hash import get_project_storage_dir

console = Console()


def status_command(project_root: Path) -> None:
    """
    Show project status including config summary and slot/container states.

    Args:
        project_root: Project root directory
    """
    config = load_config(str(project_root))

    # Config summary
    project = config.project
    global_cfg = config.global_config
    profiles = ", ".join(project.profiles) if project.profiles else "none"
    mounts_count = len(project.mounts)
    env_count = len(project.environment)
    ai_cfg = getattr(project, "ai", None)
    ai_model = getattr(ai_cfg, "model", None) if ai_cfg else None

    config_table = Table(title="Project Configuration", show_lines=False)
    config_table.add_column("Field", style="cyan", no_wrap=True)
    config_table.add_column("Value", style="white")
    config_table.add_row("Project", str(project.name))
    config_table.add_row("Profiles", profiles)
    if ai_model:
        config_table.add_row("Model", str(ai_model or "default"))
    config_table.add_row("Base Image", str(global_cfg.docker.base_image))
    config_table.add_row("Mounts", str(mounts_count))
    config_table.add_row("Environment Vars", str(env_count))
    console.print(config_table)

    # Slots summary
    storage_dir = get_project_storage_dir(project_root)
    slot_manager = SlotManager(storage_dir)
    slots = slot_manager.list_slots()

    if not slots:
        console.print("\n[dim]No slots configured.[/dim]")
        return

    try:
        container_manager = ContainerManager()
        docker_available = True
    except DockerNotFoundError:
        container_manager = None
        docker_available = False

    slot_table = Table(title="Slots", show_lines=False)
    slot_table.add_column("Slot", style="cyan", no_wrap=True)
    slot_table.add_column("Provider", style="white")
    slot_table.add_column("Container", style="white")
    slot_table.add_column("Status", style="white")
    slot_config_table = Table(title="Slot Configuration", show_lines=False)
    slot_config_table.add_column("Slot", style="cyan", no_wrap=True)
    slot_config_table.add_column("AI Provider", style="white")
    slot_config_table.add_column("Container", style="white")
    slot_config_table.add_column("Created", style="white")
    slot_config_table.add_column("Last Used", style="white")

    for slot in sorted(slots, key=lambda s: s.get("slot", 0)):
        slot_num = str(slot.get("slot", "?"))
        provider = slot.get("ai_provider", "unknown")
        container_name = slot.get("container_name", "")
        if docker_available and container_manager is not None:
            running = container_manager.is_container_running(container_name)
            status = "[green]running[/green]" if running else "[red]stopped[/red]"
        else:
            status = "[yellow]unknown (docker unavailable)[/yellow]"
        slot_table.add_row(slot_num, provider, container_name, status)

        slot_config = slot_manager.get_slot(slot.get("slot", 0)).load()
        created = ""
        last_used = ""
        if slot_config:
            created = str(slot_config.get("created_at", ""))
            last_used = str(slot_config.get("last_used", ""))
        slot_config_table.add_row(slot_num, provider, container_name, created, last_used)

    console.print(slot_table)
    console.print(slot_config_table)
