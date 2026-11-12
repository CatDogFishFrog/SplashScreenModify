import importlib
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from splashmodify.core import Parameter, ParameterKind, collect_arguments, discover_modules
from tests.fakes import FakeUserInterface

GOOD_MODULE = """
from splashmodify.core import Module

class Plugin(Module):
    id = "{id}"
    title = "{title}"
    def targets(self):
        return ()

def create_module():
    return Plugin()
"""


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.package_name = f"plugins_under_test_{id(self)}"
        self.package_dir = Path(self._directory.name) / self.package_name
        self.package_dir.mkdir()
        (self.package_dir / "__init__.py").write_text("")
        sys.path.insert(0, self._directory.name)
        self.addCleanup(sys.path.remove, self._directory.name)
        self.addCleanup(self._forget_modules)

    def _forget_modules(self):
        for name in [name for name in sys.modules if name.split(".")[0] == self.package_name]:
            del sys.modules[name]

    def add(self, file_name: str, source: str) -> None:
        path = self.package_dir / file_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source))

    def discover(self):
        importlib.invalidate_caches()
        return discover_modules(importlib.import_module(self.package_name))

    def test_finds_single_file_and_package_modules_sorted_by_title(self):
        self.add("zeta.py", GOOD_MODULE.format(id="zeta", title="Zeta"))
        self.add("alpha/__init__.py", GOOD_MODULE.format(id="alpha", title="alpha tools"))
        result = self.discover()
        self.assertEqual([module.id for module in result.modules], ["alpha", "zeta"])
        self.assertEqual(result.failures, ())

    def test_ignores_names_starting_with_underscore(self):
        self.add("_helpers.py", "raise RuntimeError('must not be imported')")
        result = self.discover()
        self.assertEqual((result.modules, result.failures), ((), ()))

    def test_broken_modules_are_reported_and_do_not_stop_the_rest(self):
        self.add("good.py", GOOD_MODULE.format(id="good", title="Good"))
        self.add("crashes.py", "raise RuntimeError('boom')")
        self.add("no_factory.py", "VALUE = 1")
        self.add("wrong_type.py", "def create_module():\n    return object()")
        result = self.discover()

        self.assertEqual([module.id for module in result.modules], ["good"])
        reasons = {failure.name: failure.reason for failure in result.failures}
        self.assertEqual(set(reasons), {"crashes", "no_factory", "wrong_type"})
        self.assertIn("boom", reasons["crashes"])
        self.assertIn("create_module", reasons["no_factory"])
        self.assertIn("must return a Module", reasons["wrong_type"])

    def test_duplicate_ids_keep_the_first_module(self):
        self.add("a_first.py", GOOD_MODULE.format(id="same", title="First"))
        self.add("b_second.py", GOOD_MODULE.format(id="same", title="Second"))
        result = self.discover()
        self.assertEqual([module.title for module in result.modules], ["First"])
        self.assertEqual([failure.name for failure in result.failures], ["b_second"])


class CollectArgumentsTests(unittest.TestCase):
    def test_collects_each_kind_in_order(self):
        ui = FakeUserInterface(texts=["hello"], files=[Path("a.png")], directories=[Path("dir")])
        parameters = [
            Parameter("text", "Text"),
            Parameter("file", "File", ParameterKind.FILE),
            Parameter("folder", "Folder", ParameterKind.DIRECTORY),
        ]
        self.assertEqual(
            collect_arguments(parameters, ui),
            {"text": "hello", "file": Path("a.png"), "folder": Path("dir")},
        )
        self.assertEqual(ui.prompts, ["Text", "File", "Folder"])

    def test_cancelling_any_parameter_cancels_everything(self):
        ui = FakeUserInterface(texts=["x"], files=[None])
        parameters = [Parameter("a", "A"), Parameter("b", "B", ParameterKind.FILE), Parameter("c", "C")]
        self.assertIsNone(collect_arguments(parameters, ui))
        self.assertEqual(ui.prompts, ["A", "B"])

    def test_no_parameters_gives_empty_arguments_not_none(self):
        self.assertEqual(collect_arguments([], FakeUserInterface()), {})

    def test_parameter_requires_name_and_prompt(self):
        with self.assertRaises(ValueError):
            Parameter("", "Prompt")


if __name__ == "__main__":
    unittest.main()
