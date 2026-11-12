"""Finding the installation folder of a product: automatic detection first, then ask the user."""

from pathlib import Path

from splashmodify.core import OperationCancelled, UserInterface
from splashmodify.system.paths import parse_user_path
from splashmodify.toolkit.jar_splash.product import JarSplashProduct


def normalize_installation_path(value: str | Path) -> Path:
    """Clean a recorded or typed location and step out of a trailing ``bin`` folder."""
    path = parse_user_path(str(value).rstrip("; "))
    if path.name.casefold() == "bin":
        path = path.parent
    return path


class InstallationFinder:
    def __init__(self, product: JarSplashProduct) -> None:
        self._product = product

    def detect(self) -> Path | None:
        """Return the installation folder if it is recorded and still contains the JAR."""
        candidate = self._recorded_location()
        if candidate is not None and self._contains_jar(candidate):
            return candidate
        return None

    def resolve(self, ui: UserInterface) -> Path:
        """Detect the installation or ask the user. Raise ``OperationCancelled`` if they give up."""
        candidate = self._recorded_location()
        if candidate is not None:
            if self._contains_jar(candidate):
                return candidate
            ui.warning(f"{self._product.jar_path} was not found in the detected folder: {candidate}")

        while True:
            entered = ui.ask_directory(f"{self._product.name} installation folder")
            if entered is None:
                raise OperationCancelled
            installation = normalize_installation_path(entered)
            if self._contains_jar(installation):
                return installation
            ui.warning(f"{self._product.jar_path} was not found in: {installation}")

    def _recorded_location(self) -> Path | None:
        recorded = self._product.locator.locate()
        if recorded is None:
            return None
        try:
            return normalize_installation_path(recorded)
        except ValueError:
            return None

    def _contains_jar(self, installation: Path) -> bool:
        return (installation / self._product.jar_path).is_file()
