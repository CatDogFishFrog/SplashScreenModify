from collections.abc import Sequence

from splashmodify.core import Action, Target
from splashmodify.system.win32_resources import update_resources
from splashmodify.toolkit.pe_splash.actions import ExtractImagesAction, ReplaceImagesAction, RestoreOriginalAction
from splashmodify.toolkit.pe_splash.locators import BinaryResolver
from splashmodify.toolkit.pe_splash.operations import ResourceWriter
from splashmodify.toolkit.pe_splash.product import PeSplashProduct


class PeSplashTarget(Target):
    """Один встановлений екземпляр продукту зі стандартними діями extract / replace / restore."""

    def __init__(
        self,
        product: PeSplashProduct,
        resolver: BinaryResolver,
        *,
        title: str | None = None,
        display_name: str | None = None,
        description: str = "",
        writer: ResourceWriter = update_resources,
    ) -> None:
        self._title = title or product.name
        self._description = description
        # Назва в повідомленнях і в папці витягнутих зображень; у меню може бути іншою («Other location...»).
        arguments = (product, display_name or self._title, resolver, writer)
        self._actions = (
            ExtractImagesAction(*arguments),
            ReplaceImagesAction(*arguments),
            RestoreOriginalAction(*arguments),
        )

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description

    def actions(self) -> Sequence[Action]:
        return self._actions
