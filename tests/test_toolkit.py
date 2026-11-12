import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from splashmodify.core import ActionContext, ActionError, OperationCancelled
from splashmodify.system.paths import parse_user_path
from splashmodify.toolkit.jar_splash import (
    JarSplashModule,
    JarSplashProduct,
    RegistryValueLocator,
    SplashCache,
    UserEnvironmentVariableLocator,
)
from splashmodify.toolkit.jar_splash.archive import backup_path
from splashmodify.toolkit.jar_splash.cache import clear_splash_cache
from splashmodify.toolkit.jar_splash.installation import InstallationFinder, normalize_installation_path
from splashmodify.system.registry import RegistryHive
from tests.fakes import FakeUserInterface
from tests.test_archive import TARGET, make_jar, make_replacement


class FixedLocator:
    def __init__(self, value: str | None) -> None:
        self._value = value

    def locate(self) -> str | None:
        return self._value


def make_product(locator, **overrides) -> JarSplashProduct:
    values = dict(name="Test IDE", jar_path="lib/product.jar", images=(TARGET,), locator=locator,
                  cache=SplashCache(vendor_dir="Vendor", folder_prefix="TestIde"))
    values.update(overrides)
    return JarSplashProduct(**values)


class PathTests(unittest.TestCase):
    def test_parse_user_path_removes_single_or_double_quotes(self):
        self.assertEqual(parse_user_path('"C:/a b/c.png"'), Path("C:/a b/c.png"))
        self.assertEqual(parse_user_path("'C:/a b/c.png'"), Path("C:/a b/c.png"))

    def test_parse_user_path_rejects_empty_input(self):
        for text in ("", "   ", '""'):
            with self.assertRaises(ValueError):
                parse_user_path(text)

    def test_normalize_strips_trailing_separator_and_bin_folder(self):
        self.assertEqual(normalize_installation_path("/opt/ide/bin;"), Path("/opt/ide"))
        self.assertEqual(normalize_installation_path('"/opt/ide/BIN"'), Path("/opt/ide"))
        self.assertEqual(normalize_installation_path("/opt/ide"), Path("/opt/ide"))


class LocatorTests(unittest.TestCase):
    def test_locators_query_the_expected_registry_location(self):
        reader = mock.Mock(return_value="value")
        self.assertEqual(UserEnvironmentVariableLocator("PyCharm", read=reader).locate(), "value")
        reader.assert_called_with(RegistryHive.CURRENT_USER, "Environment", "PyCharm")

        locator = RegistryValueLocator(RegistryHive.LOCAL_MACHINE, r"SOFTWARE\X", "Path", read=reader)
        self.assertEqual(locator.locate(), "value")
        reader.assert_called_with(RegistryHive.LOCAL_MACHINE, r"SOFTWARE\X", "Path")


class InstallationFinderTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)
        make_jar(self.root)  # creates <root>/lib/product.jar

    def test_detects_recorded_bin_folder(self):
        (self.root / "bin").mkdir()
        finder = InstallationFinder(make_product(FixedLocator(f"{self.root / 'bin'};")))
        self.assertEqual(finder.detect(), self.root)

    def test_resolve_uses_detected_installation_without_asking(self):
        ui = FakeUserInterface()
        finder = InstallationFinder(make_product(FixedLocator(str(self.root))))
        self.assertEqual(finder.resolve(ui), self.root)
        self.assertEqual(ui.prompts, [])

    def test_resolve_asks_when_nothing_is_recorded_and_accepts_bin_folder(self):
        (self.root / "bin").mkdir()
        ui = FakeUserInterface(directories=[self.root / "bin"])
        finder = InstallationFinder(make_product(FixedLocator(None)))
        self.assertEqual(finder.resolve(ui), self.root)
        self.assertEqual(len(ui.prompts), 1)

    def test_resolve_warns_about_stale_record_then_asks_again_after_a_wrong_folder(self):
        wrong = self.root / "wrong"
        wrong.mkdir()
        ui = FakeUserInterface(directories=[wrong, self.root])
        finder = InstallationFinder(make_product(FixedLocator(str(wrong))))
        self.assertEqual(finder.resolve(ui), self.root)
        self.assertEqual(len(ui.texts_of("warning")), 2)

    def test_resolve_cancels_on_empty_answer(self):
        finder = InstallationFinder(make_product(FixedLocator(None)))
        with self.assertRaises(OperationCancelled):
            finder.resolve(FakeUserInterface(directories=[None]))


class SplashCacheTests(unittest.TestCase):
    def test_clears_only_matching_product_folders(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for name in ("TestIde2024.1", "TestIde2024.2", "OtherIde2024.1"):
                (base / "Vendor" / name / "splash").mkdir(parents=True)
                (base / "Vendor" / name / "keep.txt").write_text("x")

            cleared = clear_splash_cache(SplashCache("Vendor", "TestIde"), base)

            self.assertEqual([path.parent.name for path in cleared], ["TestIde2024.1", "TestIde2024.2"])
            self.assertFalse((base / "Vendor" / "TestIde2024.1" / "splash").exists())
            self.assertTrue((base / "Vendor" / "TestIde2024.1" / "keep.txt").exists())
            self.assertTrue((base / "Vendor" / "OtherIde2024.1" / "splash").exists())

    def test_missing_vendor_folder_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(clear_splash_cache(SplashCache("Vendor", "TestIde"), Path(directory)), [])


class ActionTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)
        self.install = self.root / "install"
        self.install.mkdir()
        make_jar(self.install)
        self.local = self.root / "local"
        (self.local / "Vendor" / "TestIde2024.1" / "splash").mkdir(parents=True)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.ui = FakeUserInterface()
        self.context = ActionContext(ui=self.ui, workspace=self.workspace)

        patcher = mock.patch.dict(os.environ, {"LOCALAPPDATA": str(self.local)})
        patcher.start()
        self.addCleanup(patcher.stop)

        module = JarSplashModule(module_id="test", title="Test", description="",
                                 products=[make_product(FixedLocator(str(self.install)))])
        target = module.targets()[0]
        self.extract, self.replace, self.restore = target.actions()
        self.target = target

    def test_target_reports_detection_state(self):
        self.assertEqual(self.target.title, "Test IDE")
        self.assertEqual(self.target.description, "detected")

    def test_extract_writes_into_a_folder_per_product(self):
        self.extract.run(self.context, {})
        self.assertTrue((self.workspace / "extracted" / "Test IDE" / "splash.png").is_file())

    def test_replace_then_restore_round_trip_clears_cache(self):
        jar = self.install / "lib" / "product.jar"
        original = jar.read_bytes()
        image = make_replacement(self.root)

        self.replace.run(self.context, {"image": image})
        self.assertNotEqual(jar.read_bytes(), original)
        self.assertTrue(backup_path(jar).is_file())
        self.assertFalse((self.local / "Vendor" / "TestIde2024.1" / "splash").exists())

        self.restore.run(self.context, {})
        self.assertEqual(jar.read_bytes(), original)
        self.assertEqual(len(self.ui.texts_of("success")), 2)

    def test_restore_without_backup_only_warns(self):
        self.restore.run(self.context, {})
        self.assertEqual(self.ui.texts_of("warning"), ["No backup found. Nothing to restore."])
        self.assertTrue((self.local / "Vendor" / "TestIde2024.1" / "splash").exists())

    def test_permission_error_becomes_an_action_error(self):
        with mock.patch("splashmodify.toolkit.jar_splash.actions.replace_images", side_effect=PermissionError("locked")):
            with self.assertRaisesRegex(ActionError, "administrator"):
                self.replace.run(self.context, {"image": make_replacement(self.root)})

    def test_corrupt_archive_becomes_an_action_error(self):
        (self.install / "lib" / "product.jar").write_bytes(b"not a zip")
        with self.assertRaisesRegex(ActionError, "Operation failed"):
            self.extract.run(self.context, {})

    def test_replace_declares_an_image_file_parameter(self):
        (parameter,) = self.replace.parameters
        self.assertEqual(parameter.name, "image")


class ProductValidationTests(unittest.TestCase):
    def test_product_requires_images_and_name(self):
        with self.assertRaises(ValueError):
            make_product(FixedLocator(None), images=())
        with self.assertRaises(ValueError):
            make_product(FixedLocator(None), name=" ")

    def test_module_requires_products(self):
        with self.assertRaises(ValueError):
            JarSplashModule(module_id="x", title="X", description="", products=[])


if __name__ == "__main__":
    unittest.main()
