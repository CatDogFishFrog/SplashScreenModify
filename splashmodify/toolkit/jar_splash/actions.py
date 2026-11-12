"""The three operations offered for every JAR-based splash product."""

import zipfile
from abc import abstractmethod
from pathlib import Path

from splashmodify.core import (
    Action,
    ActionContext,
    ActionError,
    Arguments,
    Parameter,
    ParameterKind,
)
from splashmodify.system.locations import local_app_data
from splashmodify.toolkit.jar_splash.archive import extract_images, replace_images, restore_backup
from splashmodify.toolkit.jar_splash.cache import clear_splash_cache
from splashmodify.toolkit.jar_splash.installation import InstallationFinder
from splashmodify.toolkit.jar_splash.product import JarSplashProduct

IMAGE_PARAMETER = Parameter(name="image", prompt="Path to the replacement image", kind=ParameterKind.FILE)


class _JarSplashAction(Action):
    """Template: locate the installation, run the operation, translate low-level failures."""

    def __init__(self, product: JarSplashProduct, finder: InstallationFinder) -> None:
        self._product = product
        self._finder = finder

    def run(self, context: ActionContext, arguments: Arguments) -> None:
        installation = self._finder.resolve(context.ui)
        jar_file = installation / self._product.jar_path
        try:
            self.execute(context, jar_file, arguments)
        except PermissionError as error:
            raise ActionError(
                f"Permission denied: {error}. Close {self._product.name} and run this tool as administrator."
            ) from error
        except (OSError, zipfile.BadZipFile) as error:
            raise ActionError(f"Operation failed: {error}") from error

    @abstractmethod
    def execute(self, context: ActionContext, jar_file: Path, arguments: Arguments) -> None: ...

    def _clear_cache(self, context: ActionContext) -> None:
        cache = self._product.cache
        if cache is None:
            return
        try:
            cleared = clear_splash_cache(cache, local_app_data())
        except OSError as error:
            # The main operation already succeeded, so a stale cache is only worth a warning.
            context.ui.warning(f"Could not clear the splash cache: {error}")
            return
        for directory in cleared:
            context.ui.info(f"Cleared cache: {directory}")
        if not cleared:
            context.ui.info("No splash cache found; nothing to clear.")


class ExtractImagesAction(_JarSplashAction):
    title = "Extract images"
    description = "Save the current images to the workspace folder"

    def execute(self, context: ActionContext, jar_file: Path, arguments: Arguments) -> None:
        destination = context.workspace / "extracted" / self._product.name
        for file in extract_images(jar_file, self._product.images, destination):
            context.ui.success(f"Extracted {file.name}")
        context.ui.info(f"Saved to {destination}")


class ReplaceImagesAction(_JarSplashAction):
    title = "Replace images"
    description = "Use your own picture; a backup of the original is kept"
    parameters = (IMAGE_PARAMETER,)

    def execute(self, context: ActionContext, jar_file: Path, arguments: Arguments) -> None:
        result = replace_images(jar_file, self._product.images, Path(arguments[IMAGE_PARAMETER.name]))
        for entry, (width, height) in result.image_sizes.items():
            context.ui.info(f"{entry}: {width}x{height}")
        if result.backup_created:
            context.ui.info(f"Backup created: {result.backup_file}")
        else:
            context.ui.info("Backup already exists; the original backup is kept.")
        context.ui.success(f"Replaced {len(result.image_sizes)} image(s) in {jar_file.name}")
        self._clear_cache(context)
        context.ui.info(f"Restart {self._product.name} to see the change.")


class RestoreOriginalAction(_JarSplashAction):
    title = "Restore originals"
    description = "Put the original images back from the backup"

    def execute(self, context: ActionContext, jar_file: Path, arguments: Arguments) -> None:
        if not restore_backup(jar_file):
            context.ui.warning("No backup found. Nothing to restore.")
            return
        context.ui.success(f"Restored {jar_file.name} from backup")
        self._clear_cache(context)
