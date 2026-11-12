"""Android Studio is built on the IntelliJ platform but is installed and cached differently."""

from splashmodify.system.registry import RegistryHive
from splashmodify.toolkit.jar_splash import JarSplashProduct, RegistryValueLocator, SplashCache

PRODUCTS = (
    JarSplashProduct(
        name="Android Studio",
        jar_path="lib/resources.jar",
        images=("artwork/studio_splash.png", "artwork/studio_splash@2x.png"),
        locator=RegistryValueLocator(RegistryHive.LOCAL_MACHINE, r"SOFTWARE\Android Studio", "Path"),
        cache=SplashCache(vendor_dir="Google", folder_prefix="AndroidStudio"),
    ),
)
