"""CLI command implementations for aibox."""

from aibox.cli.commands.config import config_edit, config_show, config_validate
from aibox.cli.commands.images import images_list, images_prune
from aibox.cli.commands.init import init_command
from aibox.cli.commands.profile import profile_info, profile_list
from aibox.cli.commands.slot import slot_add, slot_cleanup, slot_list
from aibox.cli.commands.start import start_command
from aibox.cli.commands.status import status_command

__all__ = [
    "init_command",
    "start_command",
    "status_command",
    "profile_list",
    "profile_info",
    "slot_list",
    "slot_add",
    "slot_cleanup",
    "config_show",
    "config_validate",
    "config_edit",
    "images_list",
    "images_prune",
]
