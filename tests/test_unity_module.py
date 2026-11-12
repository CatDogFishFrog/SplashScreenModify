import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import splashmodify.modules as builtin_modules
from splashmodify.core import ActionContext, discover_modules
from splashmodify.modules.unity import create_module
from splashmodify.modules.unity.catalog import BINARY_RELATIVE_PATHS, PRODUCT
from splashmodify.modules.unity.installations import find_editor_folders, version_of
from splashmodify.modules.unity.module import UnityModule
from splashmodify.system.pe_resources import list_resources, read_resource
from splashmodify.toolkit.pe_splash.operations import backup_path, extract_images
from tests.fakes import FakeUserInterface
from tests.pe_fixtures import build_pe, fake_writer, png_bytes

RESEARCH = Path(__file__).resolve().parents[1] / "research"


class UnityTestCase(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)

    def make_editor(self, parent: Path, *names: str, dll: bool = True) -> Path:
        editor = parent.joinpath(*names, "Editor")
        editor.mkdir(parents=True)
        if dll:
            (editor / "Unity.dll").write_bytes(b"x")
        return editor


class InstallationDiscoveryTests(UnityTestCase):
    def setUp(self):
        super().setUp()
        self.program_files = self.root / "Program Files"
        self.hub_config = self.root / "UnityHub"
        self.hub_config.mkdir()
        self.hub_editors = self.program_files / "Unity" / "Hub" / "Editor"

    def find(self):
        return find_editor_folders(self.hub_config, [self.program_files])

    def test_finds_hub_editors_newest_version_first(self):
        old = self.make_editor(self.hub_editors, "2022.3.10f1")
        new = self.make_editor(self.hub_editors, "6000.3.23f1")
        mid = self.make_editor(self.hub_editors, "6000.0.9f1")
        self.assertEqual(self.find(), (new, mid, old))

    def test_numbers_are_compared_as_numbers_not_text(self):
        low = self.make_editor(self.hub_editors, "6000.3.9f1")
        high = self.make_editor(self.hub_editors, "6000.3.10f1")
        self.assertEqual(self.find(), (high, low))

    def test_ignores_folders_without_unity_dll(self):
        self.make_editor(self.hub_editors, "6000.1.0f1", dll=False)
        (self.hub_editors / "Hub-cache").mkdir()
        self.assertEqual(self.find(), ())

    def test_finds_standalone_installation(self):
        standalone = self.make_editor(self.program_files, "Unity")
        self.assertEqual(self.find(), (standalone,))
        self.assertIsNone(version_of(standalone))

    def test_reads_secondary_install_path_of_the_hub(self):
        extra = self.make_editor(self.root / "D-drive" / "Unity", "2023.2.1f1")
        (self.hub_config / "secondaryInstallPath.json").write_text(json.dumps(str(self.root / "D-drive" / "Unity")))
        self.assertEqual(self.find(), (extra,))

    def test_reads_editor_lists_of_both_hub_formats(self):
        manual = self.make_editor(self.root / "portable", "2021.3.5f1")
        legacy = self.make_editor(self.root / "legacy", "2019.4.1f1")
        (self.hub_config / "editors-v2.json").write_text(json.dumps(
            {"schemaVersion": "v2", "data": [{"version": "2021.3.5f1", "location": [str(manual / "Unity.exe")], "manual": True}]}))
        (self.hub_config / "editors.json").write_text(json.dumps(
            {"2019.4.1f1": {"version": "2019.4.1f1", "location": str(legacy / "Unity.exe")}}))
        self.assertEqual(self.find(), (manual, legacy))

    def test_same_installation_from_several_sources_is_listed_once(self):
        editor = self.make_editor(self.hub_editors, "6000.3.23f1")
        (self.hub_config / "editors-v2.json").write_text(json.dumps({"data": [{"location": [str(editor / "Unity.exe")]}]}))
        self.assertEqual(self.find(), (editor,))

    def test_broken_hub_files_are_ignored(self):
        (self.hub_config / "editors-v2.json").write_text("{ not json")
        (self.hub_config / "secondaryInstallPath.json").write_text("[1, 2]")
        editor = self.make_editor(self.hub_editors, "6000.3.23f1")
        self.assertEqual(self.find(), (editor,))

    def test_missing_hub_folder_is_not_an_error(self):
        self.assertEqual(find_editor_folders(self.root / "no-hub", [self.root / "no-pf"]), ())

    def test_version_comes_from_the_folder_name(self):
        self.assertEqual(version_of(Path("C:/Hub/Editor/6000.3.23f1/Editor")), "6000.3.23f1")
        self.assertEqual(version_of(Path("C:/Hub/Editor/2022.3.10f1c1/Editor")), "2022.3.10f1c1")
        self.assertIsNone(version_of(Path("C:/Games/MyUnity/Editor")))


class UnityModuleTests(UnityTestCase):
    def test_is_discovered_as_a_builtin_module(self):
        result = discover_modules(builtin_modules)
        self.assertEqual(result.failures, ())
        self.assertIn("unity", [module.id for module in result.modules])
        self.assertEqual(create_module().title, "Unity Editor")

    def test_lists_every_installation_and_a_manual_entry(self):
        old = self.make_editor(self.root, "2022.3.10f1")
        new = self.make_editor(self.root, "6000.3.23f1")
        module = UnityModule(find_folders=lambda: (new, old))
        targets = module.targets()
        self.assertEqual([t.title for t in targets], ["Unity 6000.3.23f1", "Unity 2022.3.10f1", "Other location..."])
        self.assertEqual(targets[0].description, str(new))

    def test_without_installations_only_the_manual_entry_remains(self):
        self.assertEqual([t.title for t in UnityModule(find_folders=lambda: ()).targets()], ["Other location..."])

    def test_list_reflects_installations_present_at_each_menu_opening(self):
        found: list[Path] = []
        module = UnityModule(find_folders=lambda: tuple(found))
        self.assertEqual(len(module.targets()), 1)
        found.append(self.make_editor(self.root, "6000.3.23f1"))
        self.assertEqual(len(module.targets()), 2)

    def test_catalog_describes_the_researched_resources(self):
        self.assertEqual([(i.type, i.name) for i in PRODUCT.images], [("BINARY", 120), ("BINARY", 121)])
        self.assertEqual(BINARY_RELATIVE_PATHS, ("Editor/Unity.dll", "Unity.dll"))

    def test_full_cycle_on_a_detected_installation(self):
        editor = self.make_editor(self.root, "6000.3.23f1", dll=False)
        dll = editor / "Unity.dll"
        original = build_pe([("BINARY", 120, 1033, png_bytes((8, 8))), ("BINARY", 121, 1033, png_bytes((16, 16))),
                             ("BINARY", 122, 1033, b"keep")])
        dll.write_bytes(original)
        picture = self.root / "picture.png"
        Image.new("RGB", (40, 40), "purple").save(picture)

        target = UnityModule(find_folders=lambda: (editor,), writer=fake_writer).targets()[0]
        actions = {action.title: action for action in target.actions()}
        ui = FakeUserInterface()
        context = ActionContext(ui=ui, workspace=self.root)

        actions["Replace images"].run(context, {"image": picture})
        self.assertNotEqual(dll.read_bytes(), original)
        self.assertTrue(backup_path(dll).is_file())
        sizes = {r.name: r.size for r in list_resources(dll)}
        self.assertEqual(sorted(sizes), [120, 121, 122])
        self.assertEqual(sizes[122], 4)

        actions["Extract images"].run(context, {})
        extracted = sorted(path.name for path in (self.root / "extracted" / "Unity 6000.3.23f1").iterdir())
        self.assertEqual(extracted, ["unity_dll_splash_id120_8x8.png", "unity_dll_splash_id121_16x16.png"])

        actions["Restore originals"].run(context, {})
        self.assertEqual(dll.read_bytes(), original)

    def test_manual_entry_asks_for_the_folder_and_accepts_a_hub_version_folder(self):
        version_folder = self.root / "6000.3.23f1"
        editor = self.make_editor(version_folder)
        (editor / "Unity.dll").write_bytes(build_pe([("BINARY", 120, 1033, png_bytes((8, 8))), ("BINARY", 121, 1033, png_bytes((16, 16)))]))
        target = UnityModule(find_folders=lambda: (), writer=fake_writer).targets()[0]
        (extract,) = [a for a in target.actions() if a.title == "Extract images"]

        ui = FakeUserInterface(directories=[version_folder])
        extract.run(ActionContext(ui=ui, workspace=self.root), {})
        self.assertEqual(len(ui.prompts), 1)
        self.assertTrue((self.root / "extracted" / "Unity Editor" / "unity_dll_splash_id120_8x8.png").is_file())


@unittest.skipUnless((RESEARCH / "Unity.dll").is_file(), "research/Unity.dll is not available")
class RealUnityDllTests(UnityTestCase):
    def test_extract_gives_the_images_documented_in_the_research(self):
        files = extract_images(RESEARCH / "Unity.dll", PRODUCT.images, self.root, PRODUCT.file_prefix)
        self.assertEqual([file.name for file in files],
                         ["unity_dll_splash_id120_575x575.png", "unity_dll_splash_id121_1150x1150.png"])
        for file in files:
            self.assertEqual(file.read_bytes(), (RESEARCH / file.name).read_bytes())


if __name__ == "__main__":
    unittest.main()
