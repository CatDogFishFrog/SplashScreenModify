"""Splash images of JetBrains IDEs."""

from splashmodify.core import Module
from splashmodify.modules.jetbrains.catalog import PRODUCTS
from splashmodify.toolkit.jar_splash import JarSplashModule


def create_module() -> Module:
    return JarSplashModule(
        module_id="jetbrains",
        title="JetBrains IDEs",
        description="IntelliJ IDEA, PyCharm, Rider and other JetBrains IDEs",
        products=PRODUCTS,
    )
