"""Contracts implemented by every module.

The application navigates a three-level tree and knows nothing else about it::

    Module  ->  Target  ->  Action
    (group)     (thing)     (operation)

For example: "JetBrains IDEs" -> "PyCharm" -> "Replace images".

``title`` and ``description`` are plain class attributes or properties; implementations
may compute them on demand, so menus always show the current state.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from splashmodify.core.parameters import Arguments, Parameter
from splashmodify.core.ui import UserInterface


@dataclass(frozen=True, slots=True)
class ActionContext:
    """Services the application offers to a running action."""

    ui: UserInterface
    workspace: Path
    """Folder next to the application where actions may write their output files."""


class Action(ABC):
    """One operation the user can run on a target."""

    @property
    @abstractmethod
    def title(self) -> str: ...

    @property
    def description(self) -> str:
        return ""

    @property
    def parameters(self) -> Sequence[Parameter]:
        """Input the application collects from the user before calling :meth:`run`."""
        return ()

    @abstractmethod
    def run(self, context: ActionContext, arguments: Arguments) -> None:
        """Perform the operation.

        Report progress through ``context.ui``. Raise ``ActionError`` for expected failures
        and ``OperationCancelled`` if the user backs out in the middle of the operation.
        """


class Target(ABC):
    """Something a module can work on, such as one application or one product."""

    @property
    @abstractmethod
    def title(self) -> str: ...

    @property
    def description(self) -> str:
        return ""

    @abstractmethod
    def actions(self) -> Sequence[Action]: ...


class Module(ABC):
    """A pluggable group of related targets. Drop a module into ``splashmodify/modules`` to add it."""

    @property
    @abstractmethod
    def id(self) -> str:
        """Stable identifier, unique among all modules."""

    @property
    @abstractmethod
    def title(self) -> str: ...

    @property
    def description(self) -> str:
        return ""

    @abstractmethod
    def targets(self) -> Sequence[Target]: ...
