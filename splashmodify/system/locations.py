"""Well-known folders."""

import os
import sys
from pathlib import Path


def application_dir() -> Path:
    """Folder that contains the executable (frozen build) or the project root (running from source)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def local_app_data() -> Path:
    """The per-user ``%LOCALAPPDATA%`` folder."""
    value = os.environ.get("LOCALAPPDATA")
    return Path(value) if value else Path.home() / "AppData" / "Local"


def roaming_app_data() -> Path:
    """Папка ``%APPDATA%`` поточного користувача."""
    value = os.environ.get("APPDATA")
    return Path(value) if value else Path.home() / "AppData" / "Roaming"


def program_files() -> tuple[Path, ...]:
    """Папки ``Program Files`` (64- і 32-бітна), без повторів."""
    folders: list[Path] = []
    for variable in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        value = os.environ.get(variable)
        if value and Path(value) not in folders:
            folders.append(Path(value))
    return tuple(folders) or (Path("C:/Program Files"),)
