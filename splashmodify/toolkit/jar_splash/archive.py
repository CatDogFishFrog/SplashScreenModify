"""Operations on image resources stored inside JAR (ZIP) archives.

These functions do no console I/O: they return results and raise ``ArchiveError``
for problems the user should hear about.
"""

import copy
import os
import shutil
import struct
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath

from PIL import Image, ImageOps

from splashmodify.core import ActionError
from splashmodify.system.files import temporary_sibling

BACKUP_SUFFIX = ".custom.backup"

INDEX_ENTRY = "__index__"
"""Name of the lookup table that JetBrains' build tools append to every IDE JAR (2024.x and newer)."""
_INDEX_RECORD_SIZE = 16
"""Index records are ``name hash (8) | size (4) | data offset (4)``, little-endian, from the start of the table."""
_INDEX_RECORD_VALUES = struct.Struct("<II")
_INDEX_RECORD_VALUES_AT = 8
_INDEX_COMMENT = struct.Struct("<BI")
"""The archive comment is ``marker (1) | absolute position inside the index data (4)``."""


class ArchiveError(ActionError):
    """The archive or the replacement image cannot be processed."""


@dataclass(frozen=True, slots=True)
class ReplaceResult:
    image_sizes: Mapping[str, tuple[int, int]]
    """Pixel size of every replaced entry."""
    backup_file: Path
    backup_created: bool
    """``False`` when a backup from an earlier run was kept untouched."""


def backup_path(jar_file: Path) -> Path:
    return jar_file.with_name(jar_file.name + BACKUP_SUFFIX)


def extract_images(jar_file: Path, entries: Sequence[str], destination: Path) -> list[Path]:
    """Save the given entries as files in ``destination`` and return their paths."""
    with zipfile.ZipFile(jar_file) as archive:
        _require_entries(archive, entries, jar_file)
        destination.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for entry in entries:
            target = destination / PurePosixPath(entry).name
            target.write_bytes(archive.read(entry))
            written.append(target)
    return written


def replace_images(jar_file: Path, entries: Sequence[str], replacement_file: Path) -> ReplaceResult:
    """Replace ``entries`` with ``replacement_file`` fitted to each original size.

    The archive is rebuilt in a temporary file, verified, and swapped in atomically.
    The original is copied to a backup once and never overwritten by later runs.
    """
    if not entries:
        raise ArchiveError("No image resources are configured for this product.")
    if not replacement_file.is_file():
        raise ArchiveError(f"Replacement image not found: {replacement_file}")

    replacements: dict[str, bytes] = {}
    sizes: dict[str, tuple[int, int]] = {}
    with Image.open(replacement_file) as replacement:
        replacement.load()
        with zipfile.ZipFile(jar_file) as archive:
            _require_entries(archive, entries, jar_file)
            for entry in entries:
                replacements[entry], sizes[entry] = _render_replacement(replacement, archive.read(entry), entry)

    backup_file = backup_path(jar_file)
    with temporary_sibling(jar_file) as temporary_file:
        _rewrite_archive(jar_file, temporary_file, replacements)

        with zipfile.ZipFile(temporary_file) as updated:
            corrupt_entry = updated.testzip()
            if corrupt_entry is not None:
                raise ArchiveError(f"Rebuilt archive failed verification at {corrupt_entry}; nothing was changed.")

        backup_created = not backup_file.exists()
        if backup_created:
            shutil.copy2(jar_file, backup_file)
        shutil.copystat(jar_file, temporary_file)
        os.replace(temporary_file, jar_file)

    return ReplaceResult(image_sizes=sizes, backup_file=backup_file, backup_created=backup_created)


def restore_backup(jar_file: Path) -> bool:
    """Put the backup back in place. Return ``False`` if there is no backup. The backup is kept."""
    backup_file = backup_path(jar_file)
    if not backup_file.is_file():
        return False
    with temporary_sibling(jar_file) as temporary_file:
        shutil.copy2(backup_file, temporary_file)
        os.replace(temporary_file, jar_file)
    return True


def _rewrite_archive(jar_file: Path, destination: Path, replacements: Mapping[str, bytes]) -> None:
    """Write a copy of ``jar_file`` to ``destination`` with ``replacements`` swapped in.

    JetBrains JARs carry an ``__index__`` entry that records where every file's data starts, and the
    archive comment points into it. Replacing an image changes the size of the data and so shifts every
    entry after it; an index that still describes the old layout makes the IDE fail while it starts.
    Such a JAR is therefore written twice: the first pass fixes the new layout, the second one stores
    the index that matches it. The index keeps its length, so the layout does not move in between.
    """
    with zipfile.ZipFile(jar_file) as source:
        if INDEX_ENTRY not in source.namelist():
            _write_archive(source, destination, replacements, source.comment)
            return
        old_layout = _data_layout(jar_file)
        old_index = source.read(INDEX_ENTRY)
        old_comment = source.comment

        with temporary_sibling(destination) as draft:
            _write_archive(source, draft, replacements, old_comment)
            new_layout = _data_layout(draft)
        new_index, new_comment = _relocate_index(
            old_index, old_comment, old_layout, new_layout, jar_file.name
        )
        _write_archive(source, destination, {**replacements, INDEX_ENTRY: new_index}, new_comment)

    _verify_index(destination)


def _write_archive(source: zipfile.ZipFile, destination: Path, replacements: Mapping[str, bytes], comment: bytes) -> None:
    with zipfile.ZipFile(destination, "w") as updated:
        updated.comment = comment
        for info in source.infolist():
            data = replacements.get(info.filename)
            if data is None:
                data = source.read(info.filename)
            # ``writestr`` rewrites the header it is given (offset, sizes), so hand it a copy.
            updated.writestr(copy.copy(info), data)


def _data_layout(jar_file: Path) -> dict[str, tuple[int, int]]:
    """Map every entry to ``(size, absolute offset of its data)``, read from the real local headers."""
    layout: dict[str, tuple[int, int]] = {}
    with zipfile.ZipFile(jar_file) as archive, open(jar_file, "rb") as raw:
        for info in archive.infolist():
            raw.seek(info.header_offset)
            header = raw.read(30)
            name_length, extra_length = struct.unpack_from("<HH", header, 26)
            layout[info.filename] = (info.file_size, info.header_offset + 30 + name_length + extra_length)
    return layout


def _relocate_index(
    index: bytes,
    comment: bytes,
    old_layout: Mapping[str, tuple[int, int]],
    new_layout: Mapping[str, tuple[int, int]],
    jar_name: str,
) -> tuple[bytes, bytes]:
    """Rewrite the size and offset of every record in ``index`` for ``new_layout``; fix the comment pointer."""
    unsupported = ArchiveError(
        f"{jar_name} has an index layout this tool does not understand; nothing was changed."
    )
    if len(comment) != _INDEX_COMMENT.size:
        raise unsupported

    entry_by_values = {values: name for name, values in old_layout.items() if name != INDEX_ENTRY}
    expected = len(entry_by_values)
    records = bytearray(index)
    matched = 0
    position = 0
    while position + _INDEX_RECORD_SIZE <= len(index):
        values_at = position + _INDEX_RECORD_VALUES_AT
        name = entry_by_values.get(_INDEX_RECORD_VALUES.unpack_from(index, values_at))
        if name is None:
            break
        _INDEX_RECORD_VALUES.pack_into(records, values_at, *new_layout[name])
        matched += 1
        position += _INDEX_RECORD_SIZE
    if matched != expected:
        raise unsupported

    marker, old_pointer = _INDEX_COMMENT.unpack(comment)
    old_start = old_layout[INDEX_ENTRY][1]
    if not old_start <= old_pointer <= old_start + len(index):
        raise unsupported
    new_pointer = new_layout[INDEX_ENTRY][1] + (old_pointer - old_start)
    return bytes(records), _INDEX_COMMENT.pack(marker, new_pointer)


def _verify_index(jar_file: Path) -> None:
    """Check that the index of the rebuilt archive matches where the data really is."""
    layout = _data_layout(jar_file)
    with zipfile.ZipFile(jar_file) as archive:
        index = archive.read(INDEX_ENTRY)
        comment = archive.comment
    marker, pointer = _INDEX_COMMENT.unpack(comment)
    start = layout[INDEX_ENTRY][1]
    expected = {values for name, values in layout.items() if name != INDEX_ENTRY}
    found = {
        _INDEX_RECORD_VALUES.unpack_from(index, offset + _INDEX_RECORD_VALUES_AT)
        for offset in range(0, len(index) - _INDEX_RECORD_SIZE + 1, _INDEX_RECORD_SIZE)
    }
    if not start <= pointer <= start + len(index) or not expected <= found:
        raise ArchiveError("The rebuilt archive has an inconsistent index; nothing was changed.")


def _require_entries(archive: zipfile.ZipFile, entries: Sequence[str], jar_file: Path) -> None:
    available = set(archive.namelist())
    missing = [entry for entry in entries if entry not in available]
    if missing:
        raise ArchiveError(f"Image resources not found in {jar_file.name}: {', '.join(missing)}")


def _render_replacement(replacement: Image.Image, original_data: bytes, entry: str) -> tuple[bytes, tuple[int, int]]:
    with Image.open(BytesIO(original_data)) as original:
        original.load()
        size, image_format = original.size, original.format
    if image_format is None:
        raise ArchiveError(f"Could not determine the image format of {entry}.")

    fitted = ImageOps.fit(replacement, size, method=Image.Resampling.LANCZOS)
    if image_format in ("JPEG", "JPG") and fitted.mode not in ("RGB", "L"):
        fitted = fitted.convert("RGB")
    buffer = BytesIO()
    fitted.save(buffer, format=image_format)
    return buffer.getvalue(), size
