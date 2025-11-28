"""aibox - Container-Based Multi-AI Development Environment."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("aibox-cli")
except PackageNotFoundError:
    # Package not installed, use fallback for development
    __version__ = "0.0.0+dev"

__author__ = "Your Name"
__email__ = "your@email.com"
