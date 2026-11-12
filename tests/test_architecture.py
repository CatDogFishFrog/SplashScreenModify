"""Enforces the dependency rules described in docs/ARCHITECTURE.md."""

import ast
import unittest
from pathlib import Path

ROOT_PACKAGE = "splashmodify"
PACKAGE_DIR = Path(__file__).resolve().parents[1] / ROOT_PACKAGE

# layer -> layers it must not import
FORBIDDEN_LAYERS = {
    "core": {"cli", "modules", "toolkit", "system", "bootstrap"},
    "system": {"core", "cli", "modules", "toolkit", "bootstrap"},
    "toolkit": {"cli", "modules", "bootstrap"},
    "cli": {"modules", "toolkit", "bootstrap"},
    "modules": {"cli", "bootstrap"},
}
# layer -> third-party packages it must not import
FORBIDDEN_THIRD_PARTY = {"core": {"PIL"}, "system": {"PIL"}, "cli": {"PIL"}}


def module_name(file: Path) -> list[str]:
    parts = [ROOT_PACKAGE, *file.relative_to(PACKAGE_DIR).with_suffix("").parts]
    return parts[:-1] if parts[-1] == "__init__" else parts


def imported_names(file: Path) -> set[str]:
    """Absolute dotted names imported by ``file`` (relative imports are resolved)."""
    current = module_name(file)
    package = current if file.name == "__init__.py" else current[:-1]
    names: set[str] = set()
    for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - (node.level - 1)]
                base = [*base, *(node.module.split(".") if node.module else [])]
            else:
                base = node.module.split(".") if node.module else []
            names.add(".".join(base))
            names.update(".".join([*base, alias.name]) for alias in node.names)
    return names


class ArchitectureTests(unittest.TestCase):
    def python_files(self, layer: str):
        return sorted((PACKAGE_DIR / layer).rglob("*.py"))

    def test_layers_respect_the_dependency_rules(self):
        for layer, forbidden in FORBIDDEN_LAYERS.items():
            for file in self.python_files(layer):
                for name in imported_names(file):
                    parts = name.split(".")
                    if parts[0] == ROOT_PACKAGE and len(parts) > 1 and parts[1] in forbidden:
                        self.fail(f"{file.relative_to(PACKAGE_DIR)}: '{layer}' must not import '{name}'")

    def test_third_party_libraries_stay_out_of_pure_layers(self):
        for layer, forbidden in FORBIDDEN_THIRD_PARTY.items():
            for file in self.python_files(layer):
                for name in imported_names(file):
                    if name.split(".")[0] in forbidden:
                        self.fail(f"{file.relative_to(PACKAGE_DIR)}: '{layer}' must not import '{name}'")

    def test_modules_do_not_depend_on_each_other(self):
        modules_dir = PACKAGE_DIR / "modules"
        for file in self.python_files("modules"):
            relative = file.relative_to(modules_dir)
            own = relative.parts[0].removesuffix(".py")
            if own == "__init__":
                continue
            for name in imported_names(file):
                parts = name.split(".")
                if parts[:2] == [ROOT_PACKAGE, "modules"] and len(parts) > 2 and parts[2] != own:
                    self.fail(f"{file.relative_to(PACKAGE_DIR)}: module '{own}' must not import '{name}'")

    def test_every_package_directory_has_an_init_file(self):
        for directory in PACKAGE_DIR.rglob("*"):
            if directory.is_dir() and directory.name != "__pycache__":
                self.assertTrue((directory / "__init__.py").is_file(), f"{directory} has no __init__.py")


if __name__ == "__main__":
    unittest.main()
