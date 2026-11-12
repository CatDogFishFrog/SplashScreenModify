"""Numbered menus with name matching, back and quit."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto

from splashmodify.cli.terminal import Console, QuitRequested

_QUIT_WORDS = {"q", "quit", "exit"}
_BACK_WORDS = {"0", "b", "back"}
_MAX_TITLE_WIDTH = 32


@dataclass(frozen=True, slots=True)
class MenuItem:
    title: str
    description: str = ""


class Command(Enum):
    BACK = auto()
    QUIT = auto()


@dataclass(frozen=True, slots=True)
class Invalid:
    message: str
    """Explanation for the user; empty when the input was blank and should simply be asked again."""


def interpret_input(text: str, titles: Sequence[str], *, allow_back: bool) -> int | Command | Invalid:
    """Interpret what the user typed: a zero-based index, a command, or a problem."""
    text = text.strip()
    if not text:
        return Invalid("")

    lowered = text.casefold()
    if lowered in _QUIT_WORDS:
        return Command.QUIT
    if allow_back and lowered in _BACK_WORDS:
        return Command.BACK
    if text.isascii() and text.isdigit():
        number = int(text)
        if 1 <= number <= len(titles):
            return number - 1
        return Invalid(f"Enter a number from 1 to {len(titles)}.")
    return _match_by_name(text, titles)


def _match_by_name(text: str, titles: Sequence[str]) -> int | Invalid:
    wanted = text.casefold()
    folded = [title.casefold() for title in titles]

    exact = [index for index, title in enumerate(folded) if title == wanted]
    if len(exact) == 1:
        return exact[0]

    matches = [index for index, title in enumerate(folded) if title.startswith(wanted)]
    if not matches:
        matches = [index for index, title in enumerate(folded) if wanted in title]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        return Invalid(f"Nothing matches '{text}'. Enter a number or part of a name.")
    names = ", ".join(titles[index] for index in matches[:4])
    return Invalid(f"'{text}' is ambiguous: {names}")


class Menu:
    def __init__(self, console: Console) -> None:
        self._console = console

    def choose(
        self,
        *,
        trail: Sequence[str],
        heading: str,
        items: Sequence[MenuItem],
        back_label: str | None,
    ) -> int | None:
        """Show the menu and return the chosen index, or ``None`` for "back".

        ``back_label`` is ``None`` on the top level, where there is nothing to go back to.
        Raises ``QuitRequested`` when the user quits.
        """
        self._render(trail, heading, items, back_label)
        titles = [item.title for item in items]
        style = self._console.style
        while True:
            answer = interpret_input(
                self._console.read(style.bold("  > ")),
                titles,
                allow_back=back_label is not None,
            )
            match answer:
                case int():
                    return answer
                case Command.BACK:
                    return None
                case Command.QUIT:
                    raise QuitRequested
                case Invalid(message=message) if message:
                    self._console.print(f"  {style.warning(message)}")

    def _render(self, trail: Sequence[str], heading: str, items: Sequence[MenuItem], back_label: str | None) -> None:
        console, style = self._console, self._console.style
        console.print()
        if trail:
            console.print(f"  {style.bold(f' {style.symbols.breadcrumb} '.join(trail))}")
        console.print(f"  {style.dim(heading)}")
        console.print()

        number_width = len(str(len(items)))
        title_width = min(max(len(item.title) for item in items), _MAX_TITLE_WIDTH)
        for number, item in enumerate(items, start=1):
            line = f"  {style.accent(str(number).rjust(number_width))}  {item.title.ljust(title_width)}"
            description = self._fit_description(item.description, 2 + number_width + 2 + title_width + 2)
            console.print(f"{line}  {style.dim(description)}" if description else line.rstrip())

        console.print()
        footer = f"{style.accent('q')} Quit"
        if back_label is not None:
            footer = f"{style.accent('0')} {back_label}    {footer}"
        console.print(f"  {footer}")

    def _fit_description(self, description: str, used_width: int) -> str:
        available = self._console.width - used_width - 1
        if len(description) <= available:
            return description
        ellipsis = self._console.style.symbols.ellipsis
        if available <= len(ellipsis) + 8:
            return ""
        return description[: available - len(ellipsis)].rstrip() + ellipsis
