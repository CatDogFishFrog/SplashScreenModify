import tempfile
import unittest
from pathlib import Path

from splashmodify.system.pe_resources import PeFormatError, find_resource, list_resources, read_resource
from tests.pe_fixtures import build_pe, png_bytes

RESEARCH = Path(__file__).resolve().parents[1] / "research"


class SyntheticPeTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)

    def write(self, data: bytes) -> Path:
        file = self.root / "app.dll"
        file.write_bytes(data)
        return file

    def test_lists_resources_with_string_and_numeric_keys(self):
        file = self.write(build_pe([("BINARY", 120, 1033, b"one"), (24, 1, 1033, b"two"), ("BINARY", 121, 1033, b"three")]))
        resources = list_resources(file)
        self.assertEqual({(r.type, r.name, r.language, r.size) for r in resources},
                         {("BINARY", 120, 1033, 3), (24, 1, 1033, 3), ("BINARY", 121, 1033, 5)})

    def test_reads_exact_data_and_finds_by_case_insensitive_type(self):
        file = self.write(build_pe([("BINARY", 120, 1033, b"payload")]))
        resource = find_resource(list_resources(file), "binary", 120)
        self.assertEqual(read_resource(file, resource), b"payload")
        self.assertIsNone(find_resource(list_resources(file), "BINARY", 999))

    def test_keeps_every_language_of_a_resource(self):
        file = self.write(build_pe([("BINARY", 1, 1033, b"en"), ("BINARY", 1, 1058, b"uk")]))
        found = {r.language: read_resource(file, r) for r in list_resources(file)}
        self.assertEqual(found, {1033: b"en", 1058: b"uk"})

    def test_file_without_resources_gives_empty_list(self):
        self.assertEqual(list_resources(self.write(build_pe([]))), [])

    def test_rejects_files_that_are_not_pe(self):
        for data in (b"", b"not a pe file at all", b"MZ" + bytes(0x100)):
            with self.subTest(size=len(data)):
                with self.assertRaises(PeFormatError):
                    list_resources(self.write(data))

    def test_rejects_truncated_file(self):
        full = build_pe([("BINARY", 1, 1033, png_bytes((8, 8)))])
        with self.assertRaises(PeFormatError):
            list_resources(self.write(full[:0x650]))


@unittest.skipUnless((RESEARCH / "Unity.dll").is_file(), "research/Unity.dll is not available")
class RealUnityDllTests(unittest.TestCase):
    """Зчитування справжнього Unity.dll має давати ті самі байти, що задокументував дослідник."""

    def test_splash_resources_match_the_research(self):
        dll = RESEARCH / "Unity.dll"
        resources = list_resources(dll)
        expected = {120: ("unity_dll_splash_id120_575x575.png", 0x04F232D0, 366472),
                    121: ("unity_dll_splash_id121_1150x1150.png", 0x04F7CA58, 1327455)}
        for name, (file_name, offset, size) in expected.items():
            with self.subTest(id=name):
                resource = find_resource(resources, "BINARY", name)
                self.assertEqual((resource.data_offset, resource.size, resource.language), (offset, size, 1033))
                self.assertEqual(read_resource(dll, resource), (RESEARCH / file_name).read_bytes())


if __name__ == "__main__":
    unittest.main()
