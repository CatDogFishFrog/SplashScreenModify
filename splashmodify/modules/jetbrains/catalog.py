"""JetBrains IDEs supported by the module. Add a line to support another one."""

from splashmodify.toolkit.jar_splash import JarSplashProduct, SplashCache, UserEnvironmentVariableLocator


def _with_retina(image: str) -> tuple[str, str]:
    """``artwork/splash.png`` -> (``artwork/splash.png``, ``artwork/splash@2x.png``)."""
    stem, dot, extension = image.rpartition(".")
    return image, f"{stem}@2x{dot}{extension}"


def _ide(name: str, *, jar: str, image: str, cache_prefix: str) -> JarSplashProduct:
    return JarSplashProduct(
        name=name,
        jar_path=jar,
        images=_with_retina(image),
        # The installer stores the bin folder in a user environment variable named after the product.
        locator=UserEnvironmentVariableLocator(name),
        cache=SplashCache(vendor_dir="JetBrains", folder_prefix=cache_prefix),
    )


PRODUCTS = (
    _ide("CLion", jar="lib/product.jar", image="artwork/clion_splash.png", cache_prefix="CLion"),
    _ide("GoLand", jar="lib/product.jar", image="artwork/splash.png", cache_prefix="GoLand"),
    _ide("IntelliJ IDEA", jar="lib/product.jar", image="idea_logo.png", cache_prefix="IntelliJIdea"),
    _ide(
        "JetBrains Rider",
        jar="lib/intellij.rider.branding.jar",
        image="rider/artwork/release/splash.png",
        cache_prefix="Rider",
    ),
    _ide("PhpStorm", jar="lib/app.jar", image="artwork/webide_logo.png", cache_prefix="PhpStorm"),
    _ide("PyCharm", jar="lib/app.jar", image="pycharm_logo.png", cache_prefix="PyCharm"),
    _ide("RubyMine", jar="lib/product-client.jar", image="artwork/rubymine_logo.png", cache_prefix="RubyMine"),
    _ide("RustRover", jar="lib/product.jar", image="artwork/splash.png", cache_prefix="RustRover"),
    _ide("WebStorm", jar="lib/app.jar", image="artwork/webide_logo.png", cache_prefix="WebStorm"),
)
