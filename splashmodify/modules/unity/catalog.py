"""Опис Unity Editor: splash-екран лежить у ресурсах ``Editor/Unity.dll``.

Дослідження (Unity 6000.3.23f1): два PNG у ресурсах типу ``BINARY`` — 575x575 (id 120)
і 1150x1150 (id 121, для HiDPI). Див. research/UNITY_SPLASH_RESEARCH.md.
"""

from splashmodify.toolkit.pe_splash import PeImageResource, PeSplashProduct

PRODUCT = PeSplashProduct(
    name="Unity Editor",
    images=(PeImageResource("BINARY", 120), PeImageResource("BINARY", 121)),
    file_prefix="unity_dll_splash",
)

BINARY_RELATIVE_PATHS = ("Editor/Unity.dll", "Unity.dll")
"""Де шукати ``Unity.dll`` у папці, яку вказав користувач: версія з Unity Hub або сама папка Editor."""
