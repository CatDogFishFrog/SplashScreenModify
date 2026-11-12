"""Декларативний опис застосунку, чиї зображення лежать у ресурсах PE-файлу (exe/dll)."""

from dataclasses import dataclass

from splashmodify.system.pe_resources import ResourceKey


@dataclass(frozen=True, slots=True)
class PeImageResource:
    """PNG-ресурс усередині PE-файлу."""

    type: ResourceKey
    """Тип ресурсу: число або рядок (у Unity це власний тип ``"BINARY"``)."""
    name: ResourceKey
    """Ідентифікатор ресурсу (у Unity це числа 120 і 121)."""

    def __str__(self) -> str:
        return f"{self.type}/{self.name}"


@dataclass(frozen=True, slots=True)
class PeSplashProduct:
    name: str
    images: tuple[PeImageResource, ...]
    file_prefix: str = "splash"
    """Початок імені файлів, які створює дія «Extract images»."""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("A product needs a name.")
        if not self.images:
            raise ValueError(f"{self.name}: at least one image resource is required.")
        if not self.file_prefix.strip():
            raise ValueError(f"{self.name}: file_prefix must not be empty.")
