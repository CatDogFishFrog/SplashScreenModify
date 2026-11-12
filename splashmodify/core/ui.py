"""Ports through which modules talk to the user.

Modules depend only on these protocols. The console implements them today;
a GUI or a test double can implement them tomorrow without touching any module.
"""

from pathlib import Path
from typing import Protocol


class Reporter(Protocol):
    """Shows messages to the user."""

    def info(self, message: str) -> None: ...

    def success(self, message: str) -> None: ...

    def warning(self, message: str) -> None: ...


class Prompter(Protocol):
    """Asks the user for input. Every ``ask_*`` method returns ``None`` when the user cancels."""

    def ask_text(self, prompt: str) -> str | None: ...

    def ask_file(self, prompt: str) -> Path | None:
        """Ask for the path of an existing file."""
        ...

    def ask_directory(self, prompt: str) -> Path | None:
        """Ask for the path of an existing directory."""
        ...


class UserInterface(Reporter, Prompter, Protocol):
    """Everything a module may use to communicate with the user."""
