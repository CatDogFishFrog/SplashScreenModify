"""Runtime discovery of modules.

A module is any sub-package (or single file) of the modules package that exposes
a ``create_module()`` function returning a :class:`Module`. Names starting with an
underscore are ignored. A module that fails to load is reported but never stops the others.
"""

import importlib
import pkgutil
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
        except Exception as error:  # noqa: BLE001 - plugin boundary: one broken module must not stop the rest
            failures.append(LoadFailure(short_name, f"{type(error).__name__}: {error}"))
            continue
        if module.id in found:
            failures.append(LoadFailure(short_name, f"module id '{module.id}' is already used by another module"))
            continue
        found[module.id] = module

    ordered = tuple(sorted(found.values(), key=lambda module: module.title.casefold()))
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
