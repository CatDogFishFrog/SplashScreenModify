"""Інструментарій для застосунків, чиї зображення лежать у ресурсах PE-файлу (exe/dll).

Опишіть застосунок через :class:`PeSplashProduct`, створіть :class:`PeSplashTarget` для кожного
встановленого екземпляра, і ціль отримає дії extract / replace / restore. Запис ресурсів
виконує Win32 API, тому replace і restore працюють лише у Windows.
"""

from splashmodify.toolkit.pe_splash.locators import AskedBinary, BinaryResolver, KnownBinary
from splashmodify.toolkit.pe_splash.operations import ResourceError, ResourceWriter
from splashmodify.toolkit.pe_splash.product import PeImageResource, PeSplashProduct
from splashmodify.toolkit.pe_splash.target import PeSplashTarget

__all__ = [
    "AskedBinary",
    "BinaryResolver",
    "KnownBinary",
    "PeImageResource",
    "PeSplashProduct",
    "PeSplashTarget",
    "ResourceError",
    "ResourceWriter",
]
