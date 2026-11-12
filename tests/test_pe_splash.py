import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

from splashmodify.core import ActionContext, ActionError, OperationCancelled
from splashmodify.system.pe_resources import list_resources, read_resource
from splashmodify.toolkit.pe_splash import (
    AskedBinary,
    KnownBinary,
    PeImageResource,
    PeSplashProduct,
    PeSplashTarget,
    ResourceError,
)
from splashmodify.toolkit.pe_splash.operations import backup_path, extract_images, replace_images, restore_backup
from tests.fakes import FakeUserInterface
from tests.pe_fixtures import build_pe, fake_writer, png_bytes, read_all

SMALL = PeImageResource("BINARY", 120)
LARGE = PeImageResource("BINARY", 121)
OTHER = (24, 1, 1033, b"<manifest/>")
PRODUCT = PeSplashProduct(name="Test App", images=(SMALL, LARGE), file_prefix="app_splash")


def image_of(data: bytes) -> Image.Image:
    image = Image.open(BytesIO(data))
    image.load()
    return image


class PeSplashTestCase(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)
        self.original_small = png_bytes((6, 6), "blue")
        self.original_large = png_bytes((12, 12), "green")
        self.binary = self.make_binary()
        self.replacement = self.root / "my picture.png"
        Image.new("RGB", (30, 20), "red").save(self.replacement)

    def make_binary(self, resources=None) -> Path:
        file = self.root / "app.dll"
        file.write_bytes(build_pe(resources or [
            ("BINARY", 120, 1033, self.original_small),
            ("BINARY", 121, 1033, self.original_large),
            OTHER,
        ]))
        return file

    def resource_data(self, file: Path, name) -> bytes:
        (resource,) = [r for r in list_resources(file) if r.name == name]
        return read_resource(file, resource)

    def leftovers(self) -> list[str]:
        return sorted(path.name for path in self.root.iterdir() if path.name.endswith(".tmp"))


class ExtractTests(PeSplashTestCase):
    def test_saves_original_images_named_by_id_and_size(self):
        files = extract_images(self.binary, PRODUCT.images, self.root / "out", "app_splash")
        self.assertEqual([file.name for file in files], ["app_splash_id120_6x6.png", "app_splash_id121_12x12.png"])
        self.assertEqual(files[0].read_bytes(), self.original_small)
        self.assertEqual(files[1].read_bytes(), self.original_large)

    def test_reports_a_missing_resource(self):
        missing = PeImageResource("BINARY", 999)
        with self.assertRaisesRegex(ResourceError, "BINARY/999"):
            extract_images(self.binary, (missing,), self.root / "out", "x")

    def test_rejects_a_resource_that_is_not_png(self):
        binary = self.make_binary([("BINARY", 120, 1033, b"plain text, not an image")])
        with self.assertRaisesRegex(ResourceError, "not a readable image"):
            extract_images(binary, (SMALL,), self.root / "out", "x")

    def test_rejects_an_image_in_another_format(self):
        buffer = BytesIO()
        Image.new("RGB", (4, 4)).save(buffer, format="JPEG")
        binary = self.make_binary([("BINARY", 120, 1033, buffer.getvalue())])
        with self.assertRaisesRegex(ResourceError, "JPEG, not PNG"):
            extract_images(binary, (SMALL,), self.root / "out", "x")


class ReplaceTests(PeSplashTestCase):
    def test_replaces_only_the_requested_resources_and_creates_backup(self):
        before = self.binary.read_bytes()
        result = replace_images(self.binary, PRODUCT.images, self.replacement, writer=fake_writer)

        self.assertEqual(result.image_sizes, {"BINARY/120": (6, 6), "BINARY/121": (12, 12)})
        self.assertTrue(result.backup_created)
        self.assertEqual(result.backup_file.read_bytes(), before)

        small, large = (image_of(self.resource_data(self.binary, name)) for name in (120, 121))
        self.assertEqual((small.size, small.format, small.mode), ((6, 6), "PNG", "RGBA"))
        self.assertEqual(large.size, (12, 12))
        self.assertEqual(small.getpixel((3, 3)), (255, 0, 0, 255))
        self.assertEqual(self.resource_data(self.binary, 1), OTHER[3])
        self.assertEqual(self.leftovers(), [])

    def test_wide_picture_is_center_cropped_to_square(self):
        picture = Image.new("RGB", (30, 20), "black")
        picture.paste("white", (10, 0, 20, 20))  # біла смуга по центру; квадрат 20x20 вирізається з x=5 до x=25
        picture.save(self.replacement)
        replace_images(self.binary, (SMALL,), self.replacement, writer=fake_writer)

        result = image_of(self.resource_data(self.binary, 120))
        self.assertEqual(result.getpixel((3, 3)), (255, 255, 255, 255))  # центр — біла смуга
        self.assertEqual(result.getpixel((0, 0)), (0, 0, 0, 255))  # краї — чорне поле, що лишилося в квадраті

    def test_second_replace_keeps_the_first_backup(self):
        original = self.binary.read_bytes()
        replace_images(self.binary, PRODUCT.images, self.replacement, writer=fake_writer)
        again = replace_images(self.binary, PRODUCT.images, self.replacement, writer=fake_writer)
        self.assertFalse(again.backup_created)
        self.assertEqual(backup_path(self.binary).read_bytes(), original)

    def test_keeps_rgb_when_the_original_has_no_alpha(self):
        binary = self.make_binary([("BINARY", 120, 1033, png_bytes((6, 6), "blue", mode="RGB"))])
        replace_images(binary, (SMALL,), self.replacement, writer=fake_writer)
        self.assertEqual(image_of(self.resource_data(binary, 120)).mode, "RGB")

    def test_transparency_of_the_replacement_is_kept(self):
        Image.new("RGBA", (6, 6), (10, 20, 30, 0)).save(self.replacement)
        replace_images(self.binary, (SMALL,), self.replacement, writer=fake_writer)
        self.assertEqual(image_of(self.resource_data(self.binary, 120)).getpixel((1, 1))[3], 0)

    def test_missing_replacement_file_changes_nothing(self):
        before = self.binary.read_bytes()
        with self.assertRaisesRegex(ResourceError, "not found"):
            replace_images(self.binary, PRODUCT.images, self.root / "nope.png", writer=fake_writer)
        self.assertEqual(self.binary.read_bytes(), before)

    def test_unreadable_replacement_changes_nothing(self):
        self.replacement.write_bytes(b"this is not an image")
        before = self.binary.read_bytes()
        with self.assertRaisesRegex(ResourceError, "Cannot read the replacement"):
            replace_images(self.binary, PRODUCT.images, self.replacement, writer=fake_writer)
        self.assertEqual(self.binary.read_bytes(), before)
        self.assertFalse(backup_path(self.binary).exists())

    def test_failed_writer_leaves_the_file_backup_and_folder_untouched(self):
        before = self.binary.read_bytes()

        def failing_writer(file, updates):
            file.write_bytes(b"half-written garbage")
            raise PermissionError("access denied")

        with self.assertRaises(PermissionError):
            replace_images(self.binary, PRODUCT.images, self.replacement, writer=failing_writer)
        self.assertEqual(self.binary.read_bytes(), before)
        self.assertFalse(backup_path(self.binary).exists())
        self.assertEqual(self.leftovers(), [])

    def test_verification_rejects_a_writer_that_damages_other_resources(self):
        before = self.binary.read_bytes()

        def damaging_writer(file, updates):
            fake_writer(file, updates)
            file.write_bytes(build_pe([(t, n, lang, b"X" if t == 24 else data) for t, n, lang, data in read_all(file)]))

        with self.assertRaisesRegex(ResourceError, "failed verification"):
            replace_images(self.binary, PRODUCT.images, self.replacement, writer=damaging_writer)
        self.assertEqual(self.binary.read_bytes(), before)
        self.assertFalse(backup_path(self.binary).exists())

    def test_verification_rejects_a_writer_that_loses_a_resource(self):
        def losing_writer(file, updates):
            file.write_bytes(build_pe([item for item in read_all(file) if item[1] != 121]))

        with self.assertRaisesRegex(ResourceError, "failed verification"):
            replace_images(self.binary, PRODUCT.images, self.replacement, writer=losing_writer)

    def test_unsupported_layout_fails_before_anything_is_written(self):
        binary = self.make_binary([OTHER])
        calls = []
        with self.assertRaisesRegex(ResourceError, "probably not supported"):
            replace_images(binary, PRODUCT.images, self.replacement, writer=lambda f, u: calls.append(u))
        self.assertEqual(calls, [])


class RestoreTests(PeSplashTestCase):
    def test_restores_the_original_and_keeps_the_backup(self):
        original = self.binary.read_bytes()
        replace_images(self.binary, PRODUCT.images, self.replacement, writer=fake_writer)
        self.assertNotEqual(self.binary.read_bytes(), original)

        self.assertTrue(restore_backup(self.binary))
        self.assertEqual(self.binary.read_bytes(), original)
        self.assertTrue(backup_path(self.binary).is_file())
        self.assertEqual(self.leftovers(), [])

    def test_without_a_backup_nothing_happens(self):
        before = self.binary.read_bytes()
        self.assertFalse(restore_backup(self.binary))
        self.assertEqual(self.binary.read_bytes(), before)


class ActionTests(PeSplashTestCase):
    def target(self, binary: Path | None = None, writer=fake_writer) -> PeSplashTarget:
        return PeSplashTarget(PRODUCT, KnownBinary(binary or self.binary), title="Test 1.0", writer=writer)

    def run_action(self, target, title, ui=None, **arguments):
        ui = ui or FakeUserInterface()
        (action,) = [a for a in target.actions() if a.title == title]
        action.run(ActionContext(ui=ui, workspace=self.root), arguments)
        return ui

    def test_target_offers_the_three_standard_actions(self):
        self.assertEqual([a.title for a in self.target().actions()], ["Extract images", "Replace images", "Restore originals"])

    def test_extract_uses_the_display_name_as_folder(self):
        ui = self.run_action(self.target(), "Extract images")
        self.assertTrue((self.root / "extracted" / "Test 1.0" / "app_splash_id120_6x6.png").is_file())
        self.assertEqual(len(ui.texts_of("success")), 2)

    def test_display_name_is_made_safe_for_a_folder_name(self):
        target = PeSplashTarget(PRODUCT, KnownBinary(self.binary), title="Other location...", display_name='Unity: "x"/y')
        self.run_action(target, "Extract images")
        self.assertTrue((self.root / "extracted" / "Unity_ _x__y").is_dir())

    def test_replace_reports_progress_and_signature_warning(self):
        ui = self.run_action(self.target(), "Replace images", image=self.replacement)
        self.assertIn("BINARY/120: 6x6", ui.texts_of("info"))
        self.assertTrue(any("Backup created" in text for text in ui.texts_of("info")))
        self.assertTrue(any("signature" in text for text in ui.texts_of("warning")))
        self.assertTrue(any("Restart Test 1.0" in text for text in ui.texts_of("info")))

    def test_restore_without_backup_only_warns(self):
        ui = self.run_action(self.target(), "Restore originals")
        self.assertEqual(ui.texts_of("warning"), ["No backup found. Nothing to restore."])

    def test_permission_error_tells_the_user_what_to_do(self):
        def denied(file, updates):
            raise PermissionError("access denied")

        with self.assertRaisesRegex(ActionError, "Close Test 1.0 and run this tool as administrator"):
            self.run_action(self.target(writer=denied), "Replace images", image=self.replacement)

    def test_other_os_errors_become_action_errors(self):
        def broken(file, updates):
            raise OSError("disk full")

        with self.assertRaisesRegex(ActionError, "disk full"):
            self.run_action(self.target(writer=broken), "Replace images", image=self.replacement)

    def test_file_that_is_not_pe_becomes_an_action_error(self):
        bad = self.root / "bad.dll"
        bad.write_bytes(b"MZ" + bytes(200))
        with self.assertRaisesRegex(ActionError, "not a valid executable image"):
            self.run_action(self.target(bad), "Extract images")

    def test_known_binary_that_disappeared_is_reported(self):
        with self.assertRaisesRegex(ActionError, "no longer exists"):
            self.run_action(self.target(self.root / "gone.dll"), "Extract images")


class ResolverTests(PeSplashTestCase):
    def test_asked_binary_retries_until_the_folder_contains_the_file(self):
        install = self.root / "install"
        (install / "Editor").mkdir(parents=True)
        (install / "Editor" / "Unity.dll").write_bytes(b"x")
        ui = FakeUserInterface(directories=[self.root / "wrong", install])
        resolved = AskedBinary("Folder", ("Editor/Unity.dll", "Unity.dll")).resolve(ui)
        self.assertEqual(resolved, install / "Editor" / "Unity.dll")
        self.assertEqual(len(ui.texts_of("warning")), 1)

    def test_asked_binary_accepts_the_second_relative_path(self):
        (self.root / "Unity.dll").write_bytes(b"x")
        resolved = AskedBinary("Folder", ("Editor/Unity.dll", "Unity.dll")).resolve(FakeUserInterface(directories=[self.root]))
        self.assertEqual(resolved, self.root / "Unity.dll")

    def test_asked_binary_cancels(self):
        with self.assertRaises(OperationCancelled):
            AskedBinary("Folder", ("Unity.dll",)).resolve(FakeUserInterface())


class ProductTests(unittest.TestCase):
    def test_product_validates_its_description(self):
        with self.assertRaises(ValueError):
            PeSplashProduct(name=" ", images=(SMALL,))
        with self.assertRaises(ValueError):
            PeSplashProduct(name="A", images=())
        with self.assertRaises(ValueError):
            PeSplashProduct(name="A", images=(SMALL,), file_prefix="")


if __name__ == "__main__":
    unittest.main()
