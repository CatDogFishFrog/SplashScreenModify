"""The example module from the documentation must keep working."""

import importlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from splashmodify.core import ActionContext, collect_arguments, discover_modules
from tests.fakes import FakeUserInterface

EXAMPLE = Path(__file__).resolve().parents[1] / "docs" / "examples" / "example_module.py"


class DocumentationExampleTests(unittest.TestCase):
    def test_example_module_is_discovered_and_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "example_plugins"
            package.mkdir()
            (package / "__init__.py").write_text("")
            shutil.copy(EXAMPLE, package / "example_module.py")
            sys.path.insert(0, directory)
            try:
                importlib.invalidate_caches()
                result = discover_modules(importlib.import_module("example_plugins"))
            finally:
                sys.path.remove(directory)
                for name in [name for name in sys.modules if name.split(".")[0] == "example_plugins"]:
                    del sys.modules[name]

            self.assertEqual(result.failures, ())
            (module,) = result.modules
            (target,) = module.targets()
            (action,) = target.actions()

            ui = FakeUserInterface(texts=["World"])
            arguments = collect_arguments(action.parameters, ui)
            action.run(ActionContext(ui=ui, workspace=Path(directory)), arguments)
            self.assertEqual((Path(directory) / "greeting.txt").read_text(encoding="utf-8"), "Hello, World!\n")


if __name__ == "__main__":
    unittest.main()
