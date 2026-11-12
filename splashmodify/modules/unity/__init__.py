"""Splash screen of Unity Editor (PNG-ресурси в Editor/Unity.dll)."""

from splashmodify.core import Module
from splashmodify.modules.unity.module import UnityModule


def create_module() -> Module:
    return UnityModule()
