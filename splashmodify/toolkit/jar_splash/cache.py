"""Clearing the splash image cache that applications keep per product version."""

import shutil
from pathlib import Path

from splashmodify.toolkit.jar_splash.product import SplashCache


def clear_splash_cache(cache: SplashCache, local_app_data: Path) -> list[Path]:
    """Delete the cached splash folder of every matching product version. Return what was deleted."""
    vendor_dir = local_app_data / cache.vendor_dir
    if not vendor_dir.is_dir():
        return []

    prefix = cache.folder_prefix.casefold()
    cleared: list[Path] = []
    for product_dir in sorted(vendor_dir.iterdir()):
        if not product_dir.is_dir() or not product_dir.name.casefold().startswith(prefix):
            continue
        splash_dir = product_dir / cache.subfolder
        if splash_dir.is_dir():
            shutil.rmtree(splash_dir)
            cleared.append(splash_dir)
    return cleared
