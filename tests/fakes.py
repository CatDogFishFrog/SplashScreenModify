"""Test doubles shared by several test modules."""

import io
from collections import deque
from collections.abc import Iterable, Sequence
from pathlib import Path

from splashmodify.cli.style import Style
from splashmodify.cli.terminal import Console
from splashmodify.core import Action, ActionContext, Arguments, Module, Parameter, Target


class FakeUserInterface:
    """Records messages and answers prompts from prepared queues (``None`` means the user cancels)."""

    def __init__(self, *, texts: Iterable[str | None] = (), files: Iterable[Path | None] = (),
                 directories: Iterable[Path | None] = ()) -> None:
        self.messages: list[tuple[str, str]] = []
        self.prompts: list[str] = []
        self._texts = deque(texts)
        self._files = deque(files)
        self._directories = deque(directories)

    def info(self, message: str) -> None:
        self.messages.append(("info", message))

    def success(self, message: str) -> None:
        self.messages.append(("success", message))

    def warning(self, message: str) -> None:
        self.messages.append(("warning", message))

    def ask_text(self, prompt: str) -> str | None:
        self.prompts.append(prompt)
        return self._texts.popleft() if self._texts else None

    def ask_file(self, prompt: str) -> Path | None:
        self.prompts.append(prompt)
        return self._files.popleft() if self._files else None

    def ask_directory(self, prompt: str) -> Path | None:
        self.prompts.append(prompt)
        return self._directories.popleft() if self._directories else None

    def texts_of(self, kind: str) -> list[str]:
        return [text for message_kind, text in self.messages if message_kind == kind]


def scripted_console(answers: Iterable[str]) -> tuple[Console, io.StringIO]:
    """A plain console fed from ``answers``; running out of answers behaves like end of input."""
    remaining = deque(answers)

    def read(_prompt: str) -> str:
        if not remaining:
            raise EOFError
        return remaining.popleft()

    output = io.StringIO()
    return Console(input_func=read, output=output, style=Style(), width=100), output


class RecordingAction(Action):
    def __init__(self, title: str = "Do it", parameters: Sequence[Parameter] = (), error: Exception | None = None) -> None:
        self._title = title
        self._parameters = tuple(parameters)
        self._error = error
        self.calls: list[Arguments] = []

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return f"{self._title} description"

    @property
    def parameters(self) -> Sequence[Parameter]:
        return self._parameters

    def run(self, context: ActionContext, arguments: Arguments) -> None:
        self.calls.append(dict(arguments))
        if self._error is not None:
            raise self._error
        context.ui.success(f"{self._title} done")


class FakeTarget(Target):
    def __init__(self, title: str, actions: Sequence[Action]) -> None:
        self._title = title
        self._actions = tuple(actions)

    @property
    def title(self) -> str:
        return self._title

    def actions(self) -> Sequence[Action]:
        return self._actions


class FakeModule(Module):
    def __init__(self, module_id: str, title: str, targets: Sequence[Target]) -> None:
        self._id = module_id
        self._title = title
        self._targets = tuple(targets)

    @property
    def id(self) -> str:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return f"{self._title} module"

    def targets(self) -> Sequence[Target]:
        return self._targets
