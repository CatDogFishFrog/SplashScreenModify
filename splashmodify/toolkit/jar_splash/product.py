"""Declarative description of an application whose splash images live inside a JAR."""

from dataclasses import dataclass

from splashmodify.toolkit.jar_splash.locators import InstallationLocator


@dataclass(frozen=True, slots=True)
class SplashCache:
    """Where an application caches its splash image and must be cleared after a change."""

    vendor_dir: str
    """Folder inside ``%LOCALAPPDATA%`` that holds one folder per product version, e.g. ``JetBrains``."""
    folder_prefix: str
    """Prefix of the per-version folders, e.g. ``PyCharm`` matches ``PyCharm2024.3``."""
    subfolder: str = "splash"


@dataclass(frozen=True, slots=True)
class JarSplashProduct:
    name: str
    jar_path: str
    """JAR location relative to the installation folder, using forward slashes."""
    images: tuple[str, ...]
    """Entry names of the images inside the JAR."""
    locator: InstallationLocator
    cache: SplashCache | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("A product needs a name.")
        if not self.jar_path.strip():
            raise ValueError(f"{self.name}: jar_path must not be empty.")
        if not self.images:
            raise ValueError(f"{self.name}: at least one image entry is required.")
