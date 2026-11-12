"""Navigation through modules, targets and actions."""

import os
import traceback
from collections.abc import Sequence
from pathlib import Path

from splashmodify import APP_TAGLINE, APP_TITLE, __version__
from splashmodify.cli.console_ui import ConsoleUserInterface
from splashmodify.cli.menu import Menu, MenuItem
from splashmodify.cli.terminal import Console, QuitRequested
from splashmodify.core import (
    Action,
    ActionContext,
    ActionError,
    LoadFailure,
    Module,
    OperationCancelled,
    Target,
    collect_arguments,
)

DEBUG_ENVIRONMENT_VARIABLE = "SPLASHMODIFY_DEBUG"


class ConsoleApp:
    """Interactive menu over whatever modules were discovered.

    Levels with a single choice are skipped, so the menu depth adapts to the installed modules.
    """

    def __init__(
        self,
        *,
        modules: Sequence[Module],
        failures: Sequence[LoadFailure],
        console: Console,
        workspace: Path,
    ) -> None:
        self._modules = tuple(modules)
        self._failures = tuple(failures)
        self._console = console
        self._ui = ConsoleUserInterface(console)
        self._menu = Menu(console)
        self._context = ActionContext(ui=self._ui, workspace=workspace)

    def run(self) -> int:
        """Run until the user quits. Return the process exit code."""
        self._show_banner()
        if not self._modules:
            self._ui.error("No modules found. Add a package to splashmodify/modules.")
            return 1
        try:
            self._browse_modules()
        except (QuitRequested, KeyboardInterrupt):
            pass
        self._console.print()
        return 0

    def _show_banner(self) -> None:
        style = self._console.style
        self._console.print()
        self._console.print(f"  {style.bold(APP_TITLE)}  {style.dim(f'v{__version__}')}")
        self._console.print(f"  {style.dim(APP_TAGLINE)}")
        for failure in self._failures:
            self._ui.warning(f"Module '{failure.name}' was not loaded: {failure.reason}")

    def _browse_modules(self) -> None:
        if len(self._modules) == 1:
            module = self._modules[0]
            self._browse_targets(module, (module.title,))
            return
        items = [MenuItem(module.title, module.description) for module in self._modules]
        while True:
            index = self._menu.choose(trail=(), heading="Choose a module", items=items, back_label=None)
            if index is None:
                return
            module = self._modules[index]
            self._browse_targets(module, (module.title,))

    def _browse_targets(self, module: Module, trail: tuple[str, ...]) -> None:
        while True:
            targets = module.targets()  # re-read each time: descriptions may reflect current state
            if not targets:
                self._ui.warning(f"{module.title} has nothing to work with.")
                return
            if len(targets) == 1:
                self._browse_actions(targets[0], _extend(trail, targets[0].title))
                return
            items = [MenuItem(target.title, target.description) for target in targets]
            index = self._menu.choose(trail=trail, heading="Choose an application", items=items, back_label="Back")
            if index is None:
                return
            self._browse_actions(targets[index], _extend(trail, targets[index].title))

    def _browse_actions(self, target: Target, trail: tuple[str, ...]) -> None:
        while True:
            actions = target.actions()
            if not actions:
                self._ui.warning(f"{target.title} has no actions.")
                return
            items = [MenuItem(action.title, action.description) for action in actions]
            index = self._menu.choose(trail=trail, heading="Choose an action", items=items, back_label="Back")
            if index is None:
                return
            self._run_action(actions[index])

    def _run_action(self, action: Action) -> None:
        self._console.print()
        try:
            arguments = collect_arguments(action.parameters, self._ui)
            if arguments is None:
                self._ui.info("Cancelled.")
                return
            action.run(self._context, arguments)
        except QuitRequested:
            raise  # the user left from inside a prompt: unwind to ``run`` instead of reporting an error
        except OperationCancelled:
            self._ui.info("Cancelled.")
        except ActionError as error:
            self._ui.error(str(error))
        except Exception as error:  # noqa: BLE001 - a failing action must not close the application
            self._ui.error(f"Unexpected error: {type(error).__name__}: {error}")
            if os.environ.get(DEBUG_ENVIRONMENT_VARIABLE):
                traceback.print_exc()


def _extend(trail: tuple[str, ...], title: str) -> tuple[str, ...]:
    """Append ``title`` unless it only repeats the last breadcrumb (a module with one same-named target)."""
    if trail and trail[-1].casefold() == title.casefold():
        return trail
    return (*trail, title)
