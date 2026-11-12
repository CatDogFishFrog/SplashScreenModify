"""Побудова мінімального PE-файлу з ресурсами для тестів (без Windows і без справжніх dll)."""

import struct
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path

from PIL import Image

from splashmodify.system.pe_resources import (
    ResourceKey,
    list_resources,
    normalize_key,
    read_resource,
)
from splashmodify.system.win32_resources import ResourceUpdate

Resource = tuple[ResourceKey, ResourceKey, int, bytes]

_HIGH = 0x80000000
_TEXT_RVA, _TEXT_RAW, _TEXT_SIZE = 0x1000, 0x400, 0x200
_RSRC_RVA, _RSRC_RAW = 0x2000, 0x600


def _align(value: int, to: int) -> int:
    return (value + to - 1) // to * to


def _ordered(keys):
    """Спершу іменовані записи (за алфавітом), потім числові (за зростанням), як вимагає PE."""
    named = sorted((key for key in keys if isinstance(key, str)), key=str.upper)
    numbers = sorted(key for key in keys if isinstance(key, int))
    return named, numbers


def _directory(keys, target_of, string_offset) -> bytes:
    named, numbers = _ordered(keys)
    out = struct.pack("<IIHHHH", 0, 0, 0, 0, len(named), len(numbers))
    for key in named:
        out += struct.pack("<II", _HIGH | string_offset[key], target_of(key))
    for key in numbers:
        out += struct.pack("<II", key, target_of(key))
    return out


def build_pe(resources: Sequence[Resource], *, text: bytes = b"\x90" * 64) -> bytes:
    """PE32+ з секціями ``.text`` і ``.rsrc``; ``resources`` — ``(тип, ім'я, мова, дані)``."""
    tree: dict = {}
    for type_key, name, language, data in resources:
        tree.setdefault(type_key, {}).setdefault(name, {})[language] = data

    def directory_size(count: int) -> int:
        return 16 + 8 * count

    offset = directory_size(len(tree))
    type_dirs, name_dirs, leaves = {}, {}, {}
    for type_key in tree:
        type_dirs[type_key] = offset
        offset += directory_size(len(tree[type_key]))
    for type_key in tree:
        for name in tree[type_key]:
            name_dirs[(type_key, name)] = offset
            offset += directory_size(len(tree[type_key][name]))
    for type_key in tree:
        for name in tree[type_key]:
            for language in tree[type_key][name]:
                leaves[(type_key, name, language)] = offset
                offset += 16
    strings = {}
    for key in {key for type_key in tree for key in (type_key, *tree[type_key]) if isinstance(key, str)}:
        strings[key] = offset
        offset += _align(2 + 2 * len(key), 4)
    offset = _align(offset, 8)
    blobs = {}
    for leaf in leaves:
        blobs[leaf] = offset
        offset += _align(len(tree[leaf[0]][leaf[1]][leaf[2]]), 8)
    rsrc_size = offset

    body = bytearray(rsrc_size)
    body[0:directory_size(len(tree))] = _directory(tree, lambda t: _HIGH | type_dirs[t], strings)
    for type_key in tree:
        at = type_dirs[type_key]
        directory = _directory(tree[type_key], lambda n, t=type_key: _HIGH | name_dirs[(t, n)], strings)
        body[at:at + len(directory)] = directory
        for name in tree[type_key]:
            at = name_dirs[(type_key, name)]
            directory = _directory(
                tree[type_key][name], lambda lang, t=type_key, n=name: leaves[(t, n, lang)], strings
            )
            body[at:at + len(directory)] = directory
    for (type_key, name, language), at in leaves.items():
        data = tree[type_key][name][language]
        body[at:at + 16] = struct.pack("<IIII", _RSRC_RVA + blobs[(type_key, name, language)], len(data), 0, 0)
        body[blobs[(type_key, name, language)]:blobs[(type_key, name, language)] + len(data)] = data
    for key, at in strings.items():
        body[at:at + 2 + 2 * len(key)] = struct.pack("<H", len(key)) + key.encode("utf-16-le")

    rsrc_raw_size = _align(rsrc_size, 0x200)
    optional = bytearray(240)
    struct.pack_into("<H", optional, 0, 0x20B)
    struct.pack_into("<II", optional, 112 + 8 * 2, _RSRC_RVA, rsrc_size)
    coff = struct.pack("<HHIIIHH", 0x8664, 2, 0, 0, 0, len(optional), 0x2022)
    sections = struct.pack("<8sIIIIIIHHI", b".text", len(text), _TEXT_RVA, _TEXT_SIZE, _TEXT_RAW, 0, 0, 0, 0, 0x60000020)
    sections += struct.pack("<8sIIIIIIHHI", b".rsrc", rsrc_size, _RSRC_RVA, rsrc_raw_size, _RSRC_RAW, 0, 0, 0, 0, 0x40000040)

    image = bytearray(_RSRC_RAW + rsrc_raw_size)
    image[0:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x40)
    header = b"PE\0\0" + coff + bytes(optional) + sections
    image[0x40:0x40 + len(header)] = header
    image[_TEXT_RAW:_TEXT_RAW + len(text)] = text
    image[_RSRC_RAW:_RSRC_RAW + rsrc_size] = body
    return bytes(image)


def read_all(file: Path) -> list[Resource]:
    return [(r.type, r.name, r.language, read_resource(file, r)) for r in list_resources(file)]


def fake_writer(file: Path, updates: Sequence[ResourceUpdate]) -> None:
    """Підміна Win32 API: перебудовує тестовий PE із новими даними ресурсів."""
    by_key = {(normalize_key(u.type), normalize_key(u.name), u.language): u.data for u in updates}
    rebuilt = [
        (t, n, lang, by_key.get((normalize_key(t), normalize_key(n), lang), data))
        for t, n, lang, data in read_all(file)
    ]
    file.write_bytes(build_pe(rebuilt))


def png_bytes(size: tuple[int, int], color="blue", mode: str = "RGBA") -> bytes:
    buffer = BytesIO()
    Image.new(mode, size, color).save(buffer, format="PNG")
    return buffer.getvalue()
