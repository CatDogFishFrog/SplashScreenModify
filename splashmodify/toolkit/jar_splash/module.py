from collections.abc import Sequence

from splashmodify.core import Module, Target
from splashmodify.toolkit.jar_splash.product import JarSplashProduct
from splashmodify.toolkit.jar_splash.target import JarSplashTarget


class JarSplashModule(Module):
    """A ready-made module for a family of products described by :class:`JarSplashProduct`."""

    def __init__(
        self,
        *,
        module_id: str,
        title: str,
        description: str,
        products: Sequence[JarSplashProduct],
    ) -> None:
        if not products:
            raise ValueError(f"Module '{module_id}' needs at least one product.")
        self._id = module_id
        self._title = title
        self._description = description
        self._targets = tuple(JarSplashTarget(product) for product in products)

    @property
    def id(self) -> str:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description

    def targets(self) -> Sequence[Target]:
        return self._targets
