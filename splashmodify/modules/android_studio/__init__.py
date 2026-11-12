"""Splash image of Android Studio."""

from splashmodify.core import Module
from splashmodify.modules.android_studio.catalog import PRODUCTS
from splashmodify.toolkit.jar_splash import JarSplashModule


def create_module() -> Module:
    return JarSplashModule(
        module_id="android_studio",
        title="Android Studio",
        description="Splash screen of Android Studio",
        products=PRODUCTS,
    )
