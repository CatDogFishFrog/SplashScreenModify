"""Declarative description of the input an action needs from the user."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from splashmodify.core.ui import Prompter


class ParameterKind(Enum):
    TEXT = auto()  # collected as ``str``
    FILE = auto()  # collected as ``Path`` of an existing file
    DIRECTORY = auto()  # collected as ``Path`` of an existing directory


@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    prompt: str
    kind: ParameterKind = ParameterKind.TEXT

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.prompt.strip():
            raise ValueError("A parameter needs a non-empty name and prompt.")


Arguments = Mapping[str, Any]
"""Collected parameter values, keyed by ``Parameter.name``."""


def collect_arguments(parameters: Sequence[Parameter], prompter: Prompter) -> dict[str, Any] | None:
    """Ask for every parameter in order. Return ``None`` if the user cancels any of them."""
    arguments: dict[str, Any] = {}
    for parameter in parameters:
        value = _ask(parameter, prompter)
        if value is None:
            return None
        arguments[parameter.name] = value
    return arguments


def _ask(parameter: Parameter, prompter: Prompter) -> Any:
    match parameter.kind:
        case ParameterKind.FILE:
            return prompter.ask_file(parameter.prompt)
        case ParameterKind.DIRECTORY:
            return prompter.ask_directory(parameter.prompt)
        case ParameterKind.TEXT:
            return prompter.ask_text(parameter.prompt)
