from collections.abc import Callable, Sequence
from pathlib import Path

from splashmodify.core import Module, Target
from splashmodify.system.locations import program_files, roaming_app_data
from splashmodify.system.win32_resources import update_resources
from splashmodify.toolkit.pe_splash import AskedBinary, KnownBinary, PeSplashTarget, ResourceWriter
from splashmodify.modules.unity.catalog import BINARY_RELATIVE_PATHS, PRODUCT
from splashmodify.modules.unity.installations import (
    HUB_DIRECTORY_NAME,
    UNITY_DLL,
    find_editor_folders,
    version_of,
)

EditorFinder = Callable[[], Sequence[Path]]


def default_editor_finder() -> Sequence[Path]:
    return find_editor_folders(roaming_app_data() / HUB_DIRECTORY_NAME, program_files())


class UnityModule(Module):
    """Кожна знайдена версія Unity Editor — окрема ціль; остання ціль питає шлях вручну.

    Список будується при кожному відкритті меню, тож нова версія з'являється без перезапуску.
    """

    def __init__(
        self, find_folders: EditorFinder = default_editor_finder, writer: ResourceWriter = update_resources
    ) -> None:
        self._find_folders = find_folders
        self._writer = writer

    @property
    def id(self) -> str:
        return "unity"

    @property
    def title(self) -> str:
        return "Unity Editor"

    @property
    def description(self) -> str:
        return "Splash screen of Unity Editor (Unity.dll)"

    def targets(self) -> Sequence[Target]:
        targets: list[Target] = [self._installed_target(folder) for folder in self._find_folders()]
        targets.append(self._manual_target())
        return targets

    def _installed_target(self, editor_folder: Path) -> Target:
        version = version_of(editor_folder)
        return PeSplashTarget(
            PRODUCT,
            KnownBinary(editor_folder / UNITY_DLL),
            title=f"Unity {version}" if version else PRODUCT.name,
            description=str(editor_folder),
            writer=self._writer,
        )

    def _manual_target(self) -> Target:
        resolver = AskedBinary(
            "Unity installation folder (the version folder or the one with Unity.exe)", BINARY_RELATIVE_PATHS
        )
        return PeSplashTarget(
            PRODUCT,
            resolver,
            title="Other location...",
            display_name=PRODUCT.name,
            description="Enter the folder yourself",
            writer=self._writer,
        )
