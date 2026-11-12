"""Пошук встановлених Unity Editor.

Джерела: списки редакторів Unity Hub (``editors-v2.json`` та старий ``editors.json``),
додаткова папка встановлення Hub (``secondaryInstallPath.json``), стандартні папки
``Program Files\\Unity\\Hub\\Editor`` і ``Program Files\\Unity\\Editor``.
Функції лише читають диск і ніколи не питають користувача.
"""

import json
import os
import re
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any

UNITY_DLL = "Unity.dll"
HUB_DIRECTORY_NAME = "UnityHub"
_VERSION_NAME = re.compile(r"^\d+(\.\d+)+\w*$")
_NUMBER = re.compile(r"\d+")


def find_editor_folders(hub_config_dir: Path, program_files: Sequence[Path]) -> tuple[Path, ...]:
    """Папки ``Editor`` (із ``Unity.dll``) усіх знайдених встановлень, найновіші версії першими."""
    candidates: list[Path] = []
    candidates.extend(_recorded_by_hub(hub_config_dir))

    roots = [folder / "Unity" / "Hub" / "Editor" for folder in program_files]
    roots.extend(_secondary_install_roots(hub_config_dir))
    for root in roots:
        candidates.extend(child / "Editor" for child in _subdirectories(root))

    candidates.extend(folder / "Unity" / "Editor" for folder in program_files)  # встановлення без Hub

    found: dict[str, Path] = {}
    for candidate in candidates:
        if (candidate / UNITY_DLL).is_file():
            found.setdefault(os.path.normcase(os.path.normpath(candidate)), candidate)
    return tuple(sorted(found.values(), key=_newest_first))


def version_of(editor_folder: Path) -> str | None:
    """Версія з імені папки Hub (``.../6000.3.23f1/Editor``), або ``None`` для інших розташувань."""
    name = editor_folder.parent.name
    return name if _VERSION_NAME.match(name) else None


def _newest_first(editor_folder: Path) -> tuple[Any, ...]:
    version = version_of(editor_folder)
    numbers = tuple(-int(number) for number in _NUMBER.findall(version)) if version else ()
    return (0 if version else 1, numbers, str(editor_folder).casefold())


def _recorded_by_hub(hub_config_dir: Path) -> Iterator[Path]:
    for file_name in ("editors-v2.json", "editors.json"):
        document = _read_json(hub_config_dir / file_name)
        for location in _locations(document):
            path = Path(location)
            if path.suffix.casefold() == ".exe":
                path = path.parent  # Hub зберігає шлях до Unity.exe, що лежить поруч із Unity.dll
            yield path
            yield path / "Editor"


def _secondary_install_roots(hub_config_dir: Path) -> Iterator[Path]:
    document = _read_json(hub_config_dir / "secondaryInstallPath.json")
    if isinstance(document, str) and document.strip():
        yield Path(document.strip())


def _locations(node: object) -> Iterator[str]:
    """Усі значення ключів ``location`` будь-де в JSON (рядок або список рядків)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "location":
                yield from _strings(value)
            else:
                yield from _locations(value)
    elif isinstance(node, list):
        for item in node:
            yield from _locations(item)


def _strings(value: object) -> Iterable[str]:
    if isinstance(value, str) and value.strip():
        yield value.strip()
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _read_json(file: Path) -> object:
    try:
        return json.loads(file.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None  # Hub не встановлено або файл пошкоджено: це не помилка, просто немає підказки


def _subdirectories(root: Path) -> list[Path]:
    try:
        return sorted(child for child in root.iterdir() if child.is_dir())
    except OSError:
        return []
