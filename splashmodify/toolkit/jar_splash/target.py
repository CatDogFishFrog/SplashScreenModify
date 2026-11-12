from collections.abc import Sequence

from splashmodify.core import Action, Target
from splashmodify.toolkit.jar_splash.actions import ExtractImagesAction, ReplaceImagesAction, RestoreOriginalAction
from splashmodify.toolkit.jar_splash.installation import InstallationFinder
from splashmodify.toolkit.jar_splash.product import JarSplashProduct


class JarSplashTarget(Target):
    """One product with the standard extract / replace / restore actions."""

    def __init__(self, product: JarSplashProduct) -> None:
        self._product = product
        self._finder = InstallationFinder(product)
        self._actions = (
            ExtractImagesAction(product, self._finder),
            ReplaceImagesAction(product, self._finder),
            RestoreOriginalAction(product, self._finder),
        )

    @property
    def title(self) -> str:
        return self._product.name

    @property
    def description(self) -> str:
        return "detected" if self._finder.detect() is not None else ""

    def actions(self) -> Sequence[Action]:
        return self._actions
