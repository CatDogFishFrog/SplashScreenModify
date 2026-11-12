"""Console front end. It knows the core contracts, never a concrete module."""

from splashmodify.cli.app import ConsoleApp
from splashmodify.cli.terminal import Console

__all__ = ["Console", "ConsoleApp"]
