"""Composition root: the only place that wires all layers together."""

import splashmodify.modules as builtin_modules
from splashmodify.cli import Console, ConsoleApp
from splashmodify.core import discover_modules
from splashmodify.system.locations import application_dir


def main() -> int:
    """Run the interactive console application and return the process exit code."""
    discovery = discover_modules(builtin_modules)
    app = ConsoleApp(
        modules=discovery.modules,
        failures=discovery.failures,
        console=Console.for_terminal(),
        workspace=application_dir(),
    )
    return app.run()
