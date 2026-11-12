"""Read-only access to the Windows registry that degrades gracefully on other systems."""

import sys
from collections.abc import Callable
from enum import Enum


class RegistryHive(Enum):
    CURRENT_USER = "HKEY_CURRENT_USER"
    LOCAL_MACHINE = "HKEY_LOCAL_MACHINE"


RegistryReader = Callable[[RegistryHive, str, str], str | None]


def read_registry_string(hive: RegistryHive, key_path: str, value_name: str) -> str | None:
    """Return a non-empty string value, or ``None`` if it is missing or the OS has no registry."""
    if sys.platform != "win32":
        return None

    import winreg

    try:
        with winreg.OpenKey(getattr(winreg, hive.value), key_path, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
    except OSError:
        return None
    return value if isinstance(value, str) and value.strip() else None
