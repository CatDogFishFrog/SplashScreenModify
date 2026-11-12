"""Runtime discovery of modules.

A module is any sub-package (or single file) of the modules package that exposes
a ``create_module()`` function returning a :class:`Module`. Names starting with an
underscore are ignored. A module that fails to load is reported but never stops the others.

When the package defines ``MODULE_FACTORIES`` (a sequence of ``create_module``
callables), those are used directly — this makes discovery work reliably inside
frozen PyInstaller executables.  Otherwise ``pkgutil.iter_modules`` is used as a
fallback (useful for test packages created on the fly).
"""

import importlib
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass
from types import ModuleType

from splashmodify.core.contracts import Module

FACTORY_NAME = "create_module"


@dataclass(frozen=True, slots=True)
class LoadFailure:
    name: str
    reason: str


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    modules: tuple[Module, ...]
    """Successfully loaded modules, sorted by title."""
    failures: tuple[LoadFailure, ...]


def discover_modules(package: ModuleType) -> DiscoveryResult:
    """Load every module found directly inside ``package``."""
    factories: tuple[Callable[[], Module], ...] | None = getattr(package, "MODULE_FACTORIES", None)
    if factories is not None:
        return _from_factories(factories)
    return _from_pkgutil(package)


# ------------------------------------------------------------------
# Explicit registration path (frozen-safe)
# ------------------------------------------------------------------

def _from_factories(factories: tuple[Callable[[], Module], ...]) -> DiscoveryResult:
    found: dict[str, Module] = {}
    failures: list[LoadFailure] = []

    for factory in factories:
        label = getattr(factory, "__module__", "<unknown>")
        try:
            module = factory()
            if not isinstance(module, Module):
                raise TypeError(f"{FACTORY_NAME}() must return a Module, not {type(module).__name__}")
            if not module.id.strip() or not module.title.strip():
                raise ValueError("module id and title must not be empty")
        except Exception as error:  # noqa: BLE001
            failures.append(LoadFailure(label, f"{type(error).__name__}: {error}"))
            continue
        if module.id in found:
            failures.append(LoadFailure(label, f"module id '{module.id}' is already used by another module"))
            continue
        found[module.id] = module

    ordered = tuple(sorted(found.values(), key=lambda m: m.title.casefold()))
    return DiscoveryResult(modules=ordered, failures=tuple(failures))


# ------------------------------------------------------------------
# pkgutil scan path (source / test packages)
# ------------------------------------------------------------------

def _from_pkgutil(package: ModuleType) -> DiscoveryResult:
    found: dict[str, Module] = {}
    failures: list[LoadFailure] = []

    entries = sorted(
        pkgutil.iter_modules(package.__path__, prefix=f"{package.__name__}."),
        key=lambda entry: entry.name,
    )
    for entry in entries:
        short_name = entry.name.rpartition(".")[2]
        if short_name.startswith("_"):
            continue
        try:
            module = _create_module(entry.name)
        except Exception as error:  # noqa: BLE001
            failures.append(LoadFailure(short_name, f"{type(error).__name__}: {error}"))
            continue
        if module.id in found:
            failures.append(LoadFailure(short_name, f"module id '{module.id}' is already used by another module"))
            continue
        found[module.id] = module

    ordered = tuple(sorted(found.values(), key=lambda m: m.title.casefold()))
    return DiscoveryResult(modules=ordered, failures=tuple(failures))


def _create_module(qualified_name: str) -> Module:
    python_module = importlib.import_module(qualified_name)
    factory = getattr(python_module, FACTORY_NAME, None)
    if not callable(factory):
        raise LookupError(f"it does not define {FACTORY_NAME}()")

    module = factory()
    if not isinstance(module, Module):
        raise TypeError(f"{FACTORY_NAME}() must return a Module, not {type(module).__name__}")
    if not module.id.strip() or not module.title.strip():
        raise ValueError("module id and title must not be empty")
    return module
