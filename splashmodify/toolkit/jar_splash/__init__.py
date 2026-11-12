"""Toolkit for applications that keep splash images inside a JAR archive.

Describe each application with :class:`JarSplashProduct`, hand the list to
:class:`JarSplashModule`, and the module gets extract / replace / restore actions.
"""

from splashmodify.toolkit.jar_splash.locators import (
    InstallationLocator,
    RegistryValueLocator,
    UserEnvironmentVariableLocator,
)
from splashmodify.toolkit.jar_splash.module import JarSplashModule
from splashmodify.toolkit.jar_splash.product import JarSplashProduct, SplashCache

__all__ = [
    "InstallationLocator",
    "JarSplashModule",
    "JarSplashProduct",
    "RegistryValueLocator",
    "SplashCache",
    "UserEnvironmentVariableLocator",
]
