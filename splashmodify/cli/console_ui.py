"""The console implementation of the ``UserInterface`` port."""

from collections.abc import Callable
from pathlib import Path

from splashmodify.cli.terminal import Console
from splashmodify.system.paths import parse_user_path


class ConsoleUserInterface:
    def __init__(self, console: Console) -> None:
        self._console = console

    # -- Reporter ---------------------------------------------------------
    def info(self, message: str) -> None:
        self._console.print(f"  {message}")

    def success(self, message: str) -> None:
        style = self._console.style
        self._console.print(f"  {style.success(style.symbols.success)} {message}")

    def warning(self, message: str) -> None:
        style = self._console.style
        self._console.print(f"  {style.warning(style.symbols.warning)} {style.warning(message)}")

    def error(self, message: str) -> None:
        style = self._console.style
        self._console.print(f"  {style.error(style.symbols.error)} {style.error(message)}")

    # -- Prompter ---------------------------------------------------------
    def ask_text(self, prompt: str) -> str | None:
        answer = self._console.read(self._format_prompt(prompt)).strip()
        return answer or None

    def ask_file(self, prompt: str) -> Path | None:
        return self._ask_path(prompt, Path.is_file, "File not found")

    def ask_directory(self, prompt: str) -> Path | None:
        return self._ask_path(prompt, Path.is_dir, "Folder not found")

    def _ask_path(self, prompt: str, exists: Callable[[Path], bool], missing_message: str) -> Path | None:
        while True:
            answer = self._console.read(self._format_prompt(prompt))
            if not answer.strip():
                return None
            try:
                path = parse_user_path(answer)
            except ValueError as error:
                self.warning(str(error))
                continue
            if exists(path):
                return path
            self.warning(f"{missing_message}: {path}")

    def _format_prompt(self, prompt: str) -> str:
        style = self._console.style
        return f"  {style.accent(style.symbols.question)} {prompt} {style.dim('(Enter to cancel)')}: "
