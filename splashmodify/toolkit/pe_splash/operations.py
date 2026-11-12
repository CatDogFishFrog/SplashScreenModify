"""Операції із зображеннями в ресурсах PE-файлу.

Функції не працюють із консоллю: повертають результати й кидають ``ResourceError``
для проблем, про які має почути користувач.
"""

import os
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from splashmodify.core import ActionError
from splashmodify.system.files import temporary_sibling
from splashmodify.system.pe_resources import PeResource, find_resource, list_resources, read_resource
from splashmodify.system.win32_resources import ResourceUpdate, update_resources
from splashmodify.toolkit.pe_splash.product import PeImageResource

BACKUP_SUFFIX = ".custom.backup"

ResourceWriter = Callable[[Path, Sequence[ResourceUpdate]], None]
"""Записує оновлення ресурсів у файл. У програмі це Win32 API, у тестах — підміна."""


class ResourceError(ActionError):
    """Ресурси файлу або замінне зображення неможливо обробити."""


@dataclass(frozen=True, slots=True)
class ReplaceResult:
    image_sizes: dict[str, tuple[int, int]]
    """Піксельний розмір кожного замінного ресурсу."""
    backup_file: Path
    backup_created: bool
    """``False``, якщо резервну копію з попереднього запуску залишено недоторканою."""


@dataclass(frozen=True, slots=True)
class _OriginalImage:
    spec: PeImageResource
    resource: PeResource
    size: tuple[int, int]
    has_alpha: bool


def backup_path(binary: Path) -> Path:
    return binary.with_name(binary.name + BACKUP_SUFFIX)


def extract_images(binary: Path, images: Sequence[PeImageResource], destination: Path, prefix: str) -> list[Path]:
    """Зберегти зображення як ``<prefix>_id<ім'я>_<ширина>x<висота>.png`` у ``destination``."""
    originals, _ = _load_originals(binary, images)
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for original in originals:
        width, height = original.size
        target = destination / f"{prefix}_id{original.spec.name}_{width}x{height}.png"
        target.write_bytes(read_resource(binary, original.resource))
        written.append(target)
    return written


def replace_images(
    binary: Path,
    images: Sequence[PeImageResource],
    replacement_file: Path,
    *,
    writer: ResourceWriter = update_resources,
) -> ReplaceResult:
    """Замінити зображення на ``replacement_file``, підігнане під розмір кожного оригіналу.

    Зміни спершу робляться в тимчасовій копії, перевіряються (нічого іншого не зачеплено,
    нові дані на місці) і лише тоді атомарно підміняють файл. Оригінал копіюється в резервну
    копію один раз і ніколи не перезаписується наступними запусками.
    """
    if not replacement_file.is_file():
        raise ResourceError(f"Replacement image not found: {replacement_file}")
    _ensure_writable(binary)
    originals, resources = _load_originals(binary, images)

    updates = [
        ResourceUpdate(
            original.spec.type,
            original.spec.name,
            original.resource.language,
            _render_replacement(replacement_file, original),
        )
        for original in originals
    ]

    backup_file = backup_path(binary)
    with temporary_sibling(binary) as draft:
        shutil.copyfile(binary, draft)
        writer(draft, updates)
        _verify(binary, draft, resources, originals, updates)

        backup_created = not backup_file.exists()
        if backup_created:
            shutil.copy2(binary, backup_file)
        shutil.copystat(binary, draft)
        os.replace(draft, binary)

    sizes = {str(original.spec): original.size for original in originals}
    return ReplaceResult(image_sizes=sizes, backup_file=backup_file, backup_created=backup_created)


def restore_backup(binary: Path) -> bool:
    """Повернути оригінал із резервної копії. ``False``, якщо копії немає. Копія зберігається."""
    backup_file = backup_path(binary)
    if not backup_file.is_file():
        return False
    _ensure_writable(binary)
    with temporary_sibling(binary) as draft:
        shutil.copy2(backup_file, draft)
        os.replace(draft, binary)
    return True


def _ensure_writable(binary: Path) -> None:
    """Завчасно виявити зайнятий файл (Unity запущено) або брак прав, не копіюючи 80 МБ дарма."""
    with open(binary, "r+b"):
        pass


def _load_originals(
    binary: Path, images: Sequence[PeImageResource]
) -> tuple[list[_OriginalImage], list[PeResource]]:
    resources = list_resources(binary)
    originals: list[_OriginalImage] = []
    for spec in images:
        resource = find_resource(resources, spec.type, spec.name)
        if resource is None:
            raise ResourceError(
                f"Resource {spec} not found in {binary.name}. This version is probably not supported."
            )
        try:
            with Image.open(BytesIO(read_resource(binary, resource))) as image:
                image.load()
                format_name, size, bands = image.format, image.size, image.getbands()
        except OSError as error:
            raise ResourceError(f"Resource {spec} in {binary.name} is not a readable image: {error}") from error
        if format_name != "PNG":
            raise ResourceError(f"Resource {spec} in {binary.name} is {format_name}, not PNG; not supported.")
        originals.append(_OriginalImage(spec, resource, size, has_alpha="A" in bands))
    return originals, resources


def _render_replacement(replacement_file: Path, original: _OriginalImage) -> bytes:
    try:
        with Image.open(replacement_file) as replacement:
            replacement.load()
            fitted = ImageOps.fit(replacement, original.size, method=Image.Resampling.LANCZOS)
    except OSError as error:
        raise ResourceError(f"Cannot read the replacement image: {error}") from error
    # Зберігаємо той самий набір каналів, що й в оригіналі (у Unity це RGBA).
    fitted = fitted.convert("RGBA" if original.has_alpha else "RGB")
    buffer = BytesIO()
    fitted.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _verify(
    binary: Path,
    draft: Path,
    before: Sequence[PeResource],
    originals: Sequence[_OriginalImage],
    updates: Sequence[ResourceUpdate],
) -> None:
    """Переконатися, що в чернетці нові дані на місці, а решта ресурсів не змінилась."""
    failure = ResourceError("The updated file failed verification; nothing was changed.")
    after = {resource.key: resource for resource in list_resources(draft)}
    expected = {original.resource.key: update.data for original, update in zip(originals, updates, strict=True)}
    if set(after) != {resource.key for resource in before}:
        raise failure
    for resource in before:
        new_data = read_resource(draft, after[resource.key])
        old_data = expected.get(resource.key)
        if old_data is None:
            old_data = read_resource(binary, resource)
        if new_data != old_data:
            raise failure
