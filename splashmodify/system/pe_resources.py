"""Читання ресурсів Win32 PE-файлів (exe/dll) без сторонніх бібліотек.

Файл ніколи не читається цілком: розбирається лише дерево ресурсів і потрібні дані,
тож 80-мегабайтний ``Unity.dll`` відкривається миттєво. Працює на будь-якій ОС,
бо це просто розбір байтів.

Дерево ресурсів має три рівні: тип -> ім'я/ідентифікатор -> мова. Тип або ім'я може бути
числом (``int``) чи рядком (``str``, наприклад ``"BINARY"``).
"""

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

ResourceKey = int | str
"""Тип чи ім'я ресурсу: число або рядок (порівнюється без урахування регістру)."""

_DOS_SIGNATURE = b"MZ"
_PE_SIGNATURE = b"PE\0\0"
_RESOURCE_DIRECTORY_INDEX = 2
_PE32_MAGIC = 0x10B
_PE32_PLUS_MAGIC = 0x20B
_DATA_DIRECTORIES_OFFSET = {_PE32_MAGIC: 96, _PE32_PLUS_MAGIC: 112}
_HIGH_BIT = 0x80000000
_MAX_DEPTH_ENTRIES = 4096  # захист від пошкоджених файлів із нескінченними чи гігантськими таблицями

_DIRECTORY = struct.Struct("<IIHHHH")  # characteristics, timestamp, major, minor, named, ids
_ENTRY = struct.Struct("<II")
_DATA_ENTRY = struct.Struct("<IIII")  # data RVA, size, code page, reserved
_SECTION = struct.Struct("<8sIIII")  # ім'я, віртуальний розмір, віртуальна адреса, розмір на диску, зміщення на диску
_SECTION_HEADER_SIZE = 40  # перші 24 байти запису розбирає _SECTION, решта нам не потрібна


class PeFormatError(ValueError):
    """Файл не є коректним PE-файлом або має пошкоджене дерево ресурсів."""


@dataclass(frozen=True, slots=True)
class PeResource:
    """Один листок дерева ресурсів."""

    type: ResourceKey
    name: ResourceKey
    language: int
    data_offset: int
    """Зміщення даних у файлі."""
    size: int

    @property
    def key(self) -> tuple[ResourceKey, ResourceKey, int]:
        return normalize_key(self.type), normalize_key(self.name), self.language


@dataclass(frozen=True, slots=True)
class _Section:
    virtual_address: int
    virtual_size: int
    raw_pointer: int
    raw_size: int


def normalize_key(value: ResourceKey) -> ResourceKey:
    """Рядкові імена в PE нечутливі до регістру, тому порівнюються у верхньому регістрі."""
    return value.upper() if isinstance(value, str) else value


def same_key(left: ResourceKey, right: ResourceKey) -> bool:
    return normalize_key(left) == normalize_key(right)


def list_resources(file: Path) -> list[PeResource]:
    """Усі ресурси файлу. Порожній список, якщо в файлі немає ресурсів."""
    with open(file, "rb") as stream:
        return _PeReader(stream).resources()


def read_resource(file: Path, resource: PeResource) -> bytes:
    with open(file, "rb") as stream:
        stream.seek(resource.data_offset)
        data = stream.read(resource.size)
    if len(data) != resource.size:
        raise PeFormatError("Дані ресурсу виходять за межі файлу.")
    return data


def find_resource(
    resources: list[PeResource], type_: ResourceKey, name: ResourceKey
) -> PeResource | None:
    """Перший ресурс із цим типом та іменем (мова не важлива)."""
    for resource in resources:
        if same_key(resource.type, type_) and same_key(resource.name, name):
            return resource
    return None


class _PeReader:
    def __init__(self, stream: BinaryIO) -> None:
        self._stream = stream
        self._sections: list[_Section] = []
        self._resource_rva = 0
        self._resource_size = 0
        self._resource_start = 0

    def resources(self) -> list[PeResource]:
        self._read_headers()
        if self._resource_rva == 0 or self._resource_size == 0:
            return []
        self._resource_start = self._file_offset(self._resource_rva)
        found: list[PeResource] = []
        for type_key, type_target in self._entries(0):
            for name_key, name_target in self._entries(self._subdirectory(type_target)):
                for language, data_target in self._entries(self._subdirectory(name_target)):
                    if not isinstance(language, int) or data_target & _HIGH_BIT:
                        raise PeFormatError("Несподівана структура дерева ресурсів.")
                    rva, size, _, _ = _DATA_ENTRY.unpack(self._read_at(self._resource_start + data_target, 16))
                    found.append(PeResource(type_key, name_key, language, self._file_offset(rva), size))
        return found

    def _read_at(self, offset: int, size: int) -> bytes:
        self._stream.seek(offset)
        data = self._stream.read(size)
        if len(data) != size:
            raise PeFormatError("Файл обірвано посеред структури PE.")
        return data

    def _read_headers(self) -> None:
        if self._read_at(0, 2) != _DOS_SIGNATURE:
            raise PeFormatError("Це не PE-файл (немає сигнатури MZ).")
        (pe_offset,) = struct.unpack("<I", self._read_at(0x3C, 4))
        if self._read_at(pe_offset, 4) != _PE_SIGNATURE:
            raise PeFormatError("Це не PE-файл (немає сигнатури PE).")

        coff = pe_offset + 4
        _, section_count, _, _, _, optional_size, _ = struct.unpack("<HHIIIHH", self._read_at(coff, 20))
        optional = coff + 20
        (magic,) = struct.unpack("<H", self._read_at(optional, 2))
        directories_at = _DATA_DIRECTORIES_OFFSET.get(magic)
        if directories_at is None:
            raise PeFormatError("Невідомий формат опційного заголовка PE.")
        if directories_at + 8 * (_RESOURCE_DIRECTORY_INDEX + 1) > optional_size:
            return  # без каталогу даних ресурсів немає
        self._resource_rva, self._resource_size = struct.unpack(
            "<II", self._read_at(optional + directories_at + 8 * _RESOURCE_DIRECTORY_INDEX, 8)
        )

        table = self._read_at(optional + optional_size, _SECTION_HEADER_SIZE * section_count)
        for index in range(section_count):
            _, virtual_size, virtual_address, raw_size, raw_pointer = _SECTION.unpack_from(table, index * _SECTION_HEADER_SIZE)
            self._sections.append(_Section(virtual_address, virtual_size, raw_pointer, raw_size))

    def _file_offset(self, rva: int) -> int:
        for section in self._sections:
            extent = max(section.virtual_size, section.raw_size)
            if section.virtual_address <= rva < section.virtual_address + extent:
                return section.raw_pointer + (rva - section.virtual_address)
        raise PeFormatError(f"Адреса RVA 0x{rva:X} не належить жодній секції.")

    @staticmethod
    def _subdirectory(target: int) -> int:
        if not target & _HIGH_BIT:
            raise PeFormatError("Несподівана структура дерева ресурсів.")
        return target & ~_HIGH_BIT

    def _entries(self, directory_offset: int) -> list[tuple[ResourceKey, int]]:
        """Записи каталогу: ``(ідентифікатор чи ім'я, зміщення від початку ресурсів)``."""
        start = self._resource_start + directory_offset
        _, _, _, _, named, ids = _DIRECTORY.unpack(self._read_at(start, _DIRECTORY.size))
        if named + ids > _MAX_DEPTH_ENTRIES:
            raise PeFormatError("Каталог ресурсів пошкоджено (забагато записів).")
        raw = self._read_at(start + _DIRECTORY.size, _ENTRY.size * (named + ids))
        entries: list[tuple[ResourceKey, int]] = []
        for index in range(named + ids):
            identifier, target = _ENTRY.unpack_from(raw, index * _ENTRY.size)
            key: ResourceKey = self._name(identifier & ~_HIGH_BIT) if identifier & _HIGH_BIT else identifier
            entries.append((key, target))
        return entries

    def _name(self, offset: int) -> str:
        (length,) = struct.unpack("<H", self._read_at(self._resource_start + offset, 2))
        return self._read_at(self._resource_start + offset + 2, length * 2).decode("utf-16-le")
