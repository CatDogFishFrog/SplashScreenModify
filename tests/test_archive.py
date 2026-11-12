import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

from splashmodify.toolkit.jar_splash.archive import (
    ArchiveError,
    backup_path,
    extract_images,
    replace_images,
    restore_backup,
)

TARGET = "artwork/splash.png"


def make_jar(root: Path, *, size: tuple[int, int] = (6, 4)) -> Path:
    lib = root / "lib"
    lib.mkdir()
    original = root / "original.png"
    Image.new("RGB", size, "blue").save(original)
    jar = lib / "product.jar"
    with zipfile.ZipFile(jar, "w") as archive:
        archive.write(original, TARGET)
        archive.writestr("keep.txt", "preserve this entry")
    return jar


def make_replacement(root: Path, name: str = "replacement image.png") -> Path:
    path = root / name
    Image.new("RGB", (4, 4), "red").save(path)
    return path


class ReplaceImagesTests(unittest.TestCase):
    def test_replaces_image_keeps_other_entries_and_creates_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jar = make_jar(root)
            result = replace_images(jar, [TARGET], make_replacement(root))

            self.assertTrue(result.backup_created)
            self.assertEqual(result.image_sizes, {TARGET: (6, 4)})
            self.assertTrue(backup_path(jar).is_file())
            with zipfile.ZipFile(jar) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(archive.read("keep.txt"), b"preserve this entry")
                with archive.open(TARGET) as file, Image.open(file) as patched:
                    self.assertEqual(patched.size, (6, 4))
                    self.assertEqual(patched.getpixel((3, 2)), (255, 0, 0))

    def test_second_run_keeps_the_first_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jar = make_jar(root)
            replace_images(jar, [TARGET], make_replacement(root))
            first_backup = backup_path(jar).read_bytes()

            result = replace_images(jar, [TARGET], make_replacement(root, "other.png"))

            self.assertFalse(result.backup_created)
            self.assertEqual(backup_path(jar).read_bytes(), first_backup)

    def test_missing_resource_changes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jar = make_jar(root)
            before = jar.read_bytes()

            with self.assertRaisesRegex(ArchiveError, "not found"):
                replace_images(jar, ["missing.png"], make_replacement(root))

            self.assertEqual(jar.read_bytes(), before)
            self.assertFalse(backup_path(jar).exists())

    def test_missing_replacement_image_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jar = make_jar(root)
            with self.assertRaisesRegex(ArchiveError, "Replacement image not found"):
                replace_images(jar, [TARGET], root / "nope.png")

    def test_no_leftover_temporary_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jar = make_jar(root)
            replace_images(jar, [TARGET], make_replacement(root))
            self.assertEqual(sorted(path.name for path in jar.parent.iterdir()),
                             ["product.jar", "product.jar.custom.backup"])


def make_indexed_jar(root: Path, *, comment_marker: int = 4) -> Path:
    """A JAR laid out like JetBrains' IDE JARs: stored entries and a trailing ``__index__`` that the comment points into."""
    original = root / "original.png"
    # A solid black PNG compresses to fewer bytes than the solid red replacement image,
    # ensuring the payload shifts and exercises index relocation.
    Image.new("RGB", (60, 40), "black").save(original)
    names = ["first.txt", TARGET, "last.txt"]
    payloads = {"first.txt": b"a" * 100, TARGET: original.read_bytes(), "last.txt": b"z" * 300}
    jar = root / "indexed.jar"

    def write(index: bytes, comment: bytes) -> None:
        with zipfile.ZipFile(jar, "w") as archive:
            archive.comment = comment
            for name in names:
                info = zipfile.ZipInfo(name)
                archive.writestr(info, payloads[name])
            archive.writestr(zipfile.ZipInfo("__index__"), index)

    tail = b"\xee" * 40
    write(b"\0" * (16 * len(names) + len(tail)), b"\0" * 5)  # first pass only to learn the layout
    layout = {}
    with zipfile.ZipFile(jar) as archive, open(jar, "rb") as raw:
        for info in archive.infolist():
            raw.seek(info.header_offset)
            name_length, extra_length = struct.unpack_from("<HH", raw.read(30), 26)
            layout[info.filename] = (info.file_size, info.header_offset + 30 + name_length + extra_length)
    records = b"".join(struct.pack("<QII", hash(name) & 0xFFFFFFFF, *layout[name]) for name in names)
    write(records + tail, struct.pack("<BI", comment_marker, layout["__index__"][1] + len(records)))
    return jar


def index_records(jar: Path) -> list[tuple[int, int]]:
    with zipfile.ZipFile(jar) as archive:
        index = archive.read("__index__")
    return [struct.unpack_from("<II", index, offset + 8) for offset in range(0, 16 * 3, 16)]


def real_layout(jar: Path) -> list[tuple[int, int]]:
    with zipfile.ZipFile(jar) as archive, open(jar, "rb") as raw:
        result = []
        for info in archive.infolist()[:3]:
            raw.seek(info.header_offset)
            name_length, extra_length = struct.unpack_from("<HH", raw.read(30), 26)
            result.append((info.file_size, info.header_offset + 30 + name_length + extra_length))
        return result


class IndexedArchiveTests(unittest.TestCase):
    def test_index_and_comment_follow_the_shifted_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jar = make_indexed_jar(root)
            self.assertEqual(index_records(jar), real_layout(jar))
            old_size = jar.stat().st_size

            replace_images(jar, [TARGET], make_replacement(root))

            self.assertNotEqual(jar.stat().st_size, old_size)  # the data really moved
            self.assertEqual(index_records(jar), real_layout(jar))
            with zipfile.ZipFile(jar) as archive:
                self.assertIsNone(archive.testzip())
                marker, pointer = struct.unpack("<BI", archive.comment)
                info = archive.getinfo("__index__")
                data_start = info.header_offset + 30 + len(b"__index__")
                self.assertEqual(marker, 4)
                self.assertEqual(pointer, data_start + 16 * 3)
                self.assertEqual(archive.read("__index__")[-40:], b"\xee" * 40)
                self.assertEqual(archive.read("last.txt"), b"z" * 300)

    def test_unknown_index_layout_is_refused_without_touching_the_jar(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jar = make_indexed_jar(root)
            with zipfile.ZipFile(jar) as archive:
                entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
            with zipfile.ZipFile(jar, "w") as archive:
                archive.comment = b"odd"
                for info, data in entries:
                    archive.writestr(info, data)
            before = jar.read_bytes()

            with self.assertRaises(ArchiveError):
                replace_images(jar, [TARGET], make_replacement(root))

            self.assertEqual(jar.read_bytes(), before)
            self.assertFalse(backup_path(jar).exists())
            self.assertEqual([path.name for path in root.iterdir() if path.name.endswith(".tmp")], [])


class RestoreBackupTests(unittest.TestCase):
    def test_restore_keeps_backup_and_ignores_neighbours(self):
        with tempfile.TemporaryDirectory() as directory:
            lib = Path(directory)
            jar = lib / "product.jar"
            backup = backup_path(jar)
            neighbour = lib / "other.jar.custom.backup"
            jar.write_bytes(b"modified")
            backup.write_bytes(b"original")
            neighbour.write_bytes(b"neighbour")

            self.assertTrue(restore_backup(jar))

            self.assertEqual(jar.read_bytes(), b"original")
            self.assertTrue(backup.is_file())
            self.assertEqual(neighbour.read_bytes(), b"neighbour")

    def test_without_backup_reports_false_and_changes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory) / "product.jar"
            jar.write_bytes(b"current")
            self.assertFalse(restore_backup(jar))
            self.assertEqual(jar.read_bytes(), b"current")


class ExtractImagesTests(unittest.TestCase):
    def test_extracts_entries_by_file_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jar = make_jar(root)
            files = extract_images(jar, [TARGET], root / "out")
            self.assertEqual([file.name for file in files], ["splash.png"])
            self.assertTrue(files[0].is_file())

    def test_missing_entry_is_reported_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jar = make_jar(root)
            with self.assertRaisesRegex(ArchiveError, "not found"):
                extract_images(jar, ["missing.png"], root / "out")
            self.assertFalse((root / "out").exists())


if __name__ == "__main__":
    unittest.main()
