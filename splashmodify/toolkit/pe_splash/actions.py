"""Три операції, що пропонуються для кожного продукту із зображеннями в PE-ресурсах."""

import re
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
from splashmodify.system.pe_resources import PeFormatError
from splashmodify.system.win32_resources import update_resources
from splashmodify.toolkit.pe_splash.locators import BinaryResolver
from splashmodify.toolkit.pe_splash.operations import (
    ResourceWriter,
    extract_images,
    replace_images,
    restore_backup,
)
from splashmodify.toolkit.pe_splash.product import PeSplashProduct

IMAGE_PARAMETER = Parameter(name="image", prompt="Path to the replacement image", kind=ParameterKind.FILE)

_FORBIDDEN_IN_FILE_NAMES = re.compile(r'[<>:"/\\|?*]')


class _PeSplashAction(Action):
    """Шаблон: знайти файл, виконати операцію, перекласти низькорівневі збої."""

    def __init__(
        self,
        product: PeSplashProduct,
        display_name: str,
        resolver: BinaryResolver,
        writer: ResourceWriter = update_resources,
    ) -> None:
        self._product = product
        self._display_name = display_name
        self._resolver = resolver
        self._writer = writer

    def run(self, context: ActionContext, arguments: Arguments) -> None:
        binary = self._resolver.resolve(context.ui)
        try:
            self.execute(context, binary, arguments)
        except PermissionError as error:
            raise ActionError(
                f"Permission denied: {error}. Close {self._display_name} and run this tool as administrator."
            ) from error
        except PeFormatError as error:
            raise ActionError(f"{binary.name} is not a valid executable image: {error}") from error
        except OSError as error:
            raise ActionError(f"Operation failed: {error}") from error

    @abstractmethod
    def execute(self, context: ActionContext, binary: Path, arguments: Arguments) -> None: ...


class ExtractImagesAction(_PeSplashAction):
    title = "Extract images"
    description = "Save the current images to the workspace folder"

    def execute(self, context: ActionContext, binary: Path, arguments: Arguments) -> None:
        folder_name = _FORBIDDEN_IN_FILE_NAMES.sub("_", self._display_name)
        destination = context.workspace / "extracted" / folder_name
        for file in extract_images(binary, self._product.images, destination, self._product.file_prefix):
            context.ui.success(f"Extracted {file.name}")
        context.ui.info(f"Saved to {destination}")


class ReplaceImagesAction(_PeSplashAction):
    title = "Replace images"
    description = "Use your own picture; a backup of the original is kept"
    parameters = (IMAGE_PARAMETER,)

    def execute(self, context: ActionContext, binary: Path, arguments: Arguments) -> None:
        context.ui.info(f"Updating {binary.name}; this can take a few seconds...")
        result = replace_images(
            binary, self._product.images, Path(arguments[IMAGE_PARAMETER.name]), writer=self._writer
        )
        for resource, (width, height) in result.image_sizes.items():
            context.ui.info(f"{resource}: {width}x{height}")
        if result.backup_created:
            context.ui.info(f"Backup created: {result.backup_file}")
        else:
            context.ui.info("Backup already exists; the original backup is kept.")
        context.ui.success(f"Replaced {len(result.image_sizes)} image(s) in {binary.name}")
        context.ui.warning(
            f"The digital signature of {binary.name} is no longer valid; Windows may warn about it, but launching is not blocked."
        )
        context.ui.info(f"Restart {self._display_name} to see the change.")


class RestoreOriginalAction(_PeSplashAction):
    title = "Restore originals"
    description = "Put the original images back from the backup"

    def execute(self, context: ActionContext, binary: Path, arguments: Arguments) -> None:
        if not restore_backup(binary):
            context.ui.warning("No backup found. Nothing to restore.")
            return
        context.ui.success(f"Restored {binary.name} from backup")

