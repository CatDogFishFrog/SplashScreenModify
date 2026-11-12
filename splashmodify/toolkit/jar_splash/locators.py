"""Strategies that find where an application is installed.

A locator only reports what the installer recorded; it does not verify the result
and never talks to the user.
"""

from typing import Protocol

from splashmodify.system.registry import RegistryHive, RegistryReader, read_registry_string


class InstallationLocator(Protocol):
    def locate(self) -> str | None:
        """Return the raw location text recorded by the installer, or ``None`` if unknown."""
        ...


class UserEnvironmentVariableLocator:
    """Reads a per-user environment variable stored in the registry (``HKCU\\Environment``).

    JetBrains installers publish the product's ``bin`` folder this way.
    """

    def __init__(self, variable: str, *, read: RegistryReader = read_registry_string) -> None:
        self._variable = variable
        self._read = read

    def locate(self) -> str | None:
        return self._read(RegistryHive.CURRENT_USER, "Environment", self._variable)


class RegistryValueLocator:
    """Reads an arbitrary string value from the registry."""

    def __init__(
        self,
        hive: RegistryHive,
        key_path: str,
        value_name: str,
        *,
        read: RegistryReader = read_registry_string,
    ) -> None:
        self._hive = hive
        self._key_path = key_path
        self._value_name = value_name
        self._read = read

    def locate(self) -> str | None:
        return self._read(self._hive, self._key_path, self._value_name)
