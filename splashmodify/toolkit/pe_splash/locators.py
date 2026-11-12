"""Як отримати шлях до PE-файлу, який треба змінити."""

from pathlib import Path
from typing import Protocol

from splashmodify.core import ActionError, OperationCancelled, UserInterface


class BinaryResolver(Protocol):
    def resolve(self, ui: UserInterface) -> Path:
        """Повернути шлях до існуючого файлу або запитати його в користувача."""
        ...


class KnownBinary:
    """Шлях уже відомий (знайдений автоматично); перевіряється, що файл досі існує."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def resolve(self, ui: UserInterface) -> Path:
        if not self._path.is_file():
            raise ActionError(f"File no longer exists: {self._path}")
        return self._path


class AskedBinary:
    """Питає папку встановлення, доки в ній не знайдеться файл за одним зі шляхів ``relative_paths``."""

    def __init__(self, prompt: str, relative_paths: tuple[str, ...]) -> None:
        if not relative_paths:
            raise ValueError("At least one relative path is required.")
        self._prompt = prompt
        self._relative_paths = relative_paths

    def resolve(self, ui: UserInterface) -> Path:
        while True:
            folder = ui.ask_directory(self._prompt)
            if folder is None:
                raise OperationCancelled
            for relative in self._relative_paths:
                candidate = folder / relative
                if candidate.is_file():
                    return candidate
            ui.warning(f"{' or '.join(self._relative_paths)} was not found in: {folder}")
