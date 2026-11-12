"""Запис ресурсів у PE-файл через Win32 API (``BeginUpdateResource`` / ``UpdateResource``).

Саме Windows перебудовує секцію ресурсів і всі зміщення, тому власного запису PE ми не пишемо.
Модуль завантажує ``kernel32`` лише під час виклику, тож його можна імпортувати на будь-якій ОС;
поза Windows виклик завершується зрозумілою помилкою.
"""

import ctypes
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from splashmodify.system.pe_resources import ResourceKey


@dataclass(frozen=True, slots=True)
class ResourceUpdate:
    """Нові дані для ресурсу. Мова має збігатися з мовою наявного ресурсу, інакше з'явиться дублікат."""

    type: ResourceKey
    name: ResourceKey
    language: int
    data: bytes


def update_resources(file: Path, updates: Sequence[ResourceUpdate], *, kernel32: Any = None) -> None:
    """Записати всі ``updates`` у ``file`` однією операцією: або все, або нічого.

    ``OSError`` (зокрема ``PermissionError``) сигналізує про відмову Windows: файл зайнятий
    або немає прав адміністратора. ``kernel32`` можна підмінити в тестах.
    """
    if not updates:
        return
    api = kernel32 if kernel32 is not None else _load_kernel32()

    handle = api.BeginUpdateResourceW(str(file), False)
    if not handle:
        raise _last_error(api, "BeginUpdateResource")
    finished = False
    try:
        for update in updates:
            _apply(api, handle, update)
        finished = True
    finally:
        # Скасувати зміни, якщо хоч одне оновлення не вдалося: файл залишиться без змін.
        committed = api.EndUpdateResourceW(handle, not finished)
    if not committed:
        raise _last_error(api, "EndUpdateResource")


def _apply(api: Any, handle: Any, update: ResourceUpdate) -> None:
    # Числові ідентифікатори передаються як MAKEINTRESOURCE (значення замість вказівника),
    # рядкові як вказівник на UTF-16 рядок, який має жити до кінця виклику.
    keepalive: list[Any] = []
    type_argument = _resource_argument(update.type, keepalive)
    name_argument = _resource_argument(update.name, keepalive)
    buffer = ctypes.create_string_buffer(update.data, len(update.data))
    if not api.UpdateResourceW(handle, type_argument, name_argument, update.language, buffer, len(update.data)):
        raise _last_error(api, "UpdateResource")


def _resource_argument(key: ResourceKey, keepalive: list[Any]) -> Any:
    if isinstance(key, int):
        return ctypes.c_void_p(key)
    text = ctypes.c_wchar_p(key)
    keepalive.append(text)
    return ctypes.cast(text, ctypes.c_void_p)


def _load_kernel32() -> Any:
    if sys.platform != "win32":
        raise OSError("Запис ресурсів PE доступний лише у Windows.")

    from ctypes import wintypes

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.BeginUpdateResourceW.argtypes = (wintypes.LPCWSTR, wintypes.BOOL)
    api.BeginUpdateResourceW.restype = wintypes.HANDLE
    api.UpdateResourceW.argtypes = (
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.WORD,
        ctypes.c_void_p,
        wintypes.DWORD,
    )
    api.UpdateResourceW.restype = wintypes.BOOL
    api.EndUpdateResourceW.argtypes = (wintypes.HANDLE, wintypes.BOOL)
    api.EndUpdateResourceW.restype = wintypes.BOOL
    return api


def _last_error(api: Any, function: str) -> OSError:
    """Помилка Windows як ``OSError``; підклас зберігається (код 5 -> ``PermissionError``)."""
    if sys.platform != "win32":
        return OSError(f"{function} failed")
    error = ctypes.WinError(ctypes.get_last_error())
    return type(error)(error.errno, f"{function}: {error.strerror}")
