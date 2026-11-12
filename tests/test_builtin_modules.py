import unittest

import splashmodify.modules as builtin_modules
from splashmodify.core import discover_modules
from splashmodify.modules.android_studio.catalog import PRODUCTS as ANDROID_PRODUCTS
from splashmodify.modules.jetbrains.catalog import PRODUCTS as JETBRAINS_PRODUCTS


class BuiltinModulesTests(unittest.TestCase):
    def test_builtin_modules_load_without_failures(self):
        result = discover_modules(builtin_modules)
        self.assertEqual(result.failures, ())
        self.assertEqual([module.id for module in result.modules], ["android_studio", "jetbrains", "unity"])

    def test_every_target_offers_extract_replace_restore(self):
        for module in discover_modules(builtin_modules).modules:
            for target in module.targets():
                self.assertEqual(
                    [action.title for action in target.actions()],
                    ["Extract images", "Replace images", "Restore originals"],
                    f"{module.id}/{target.title}",
                )

    def test_catalogs_are_consistent(self):
        for products in (JETBRAINS_PRODUCTS, ANDROID_PRODUCTS):
            names = [product.name for product in products]
            self.assertEqual(len(names), len(set(names)), "duplicate product names")
            for product in products:
                with self.subTest(product=product.name):
                    self.assertEqual(len(product.images), 2)
                    self.assertTrue(product.images[1].replace("@2x", "") == product.images[0])
                    self.assertIsNotNone(product.cache)

    def test_jetbrains_catalog_keeps_the_original_configuration(self):
        by_name = {product.name: product for product in JETBRAINS_PRODUCTS}
        self.assertEqual(set(by_name), {"CLion", "GoLand", "IntelliJ IDEA", "JetBrains Rider", "PhpStorm",
                                        "PyCharm", "RubyMine", "RustRover", "WebStorm"})
        rider = by_name["JetBrains Rider"]
        self.assertEqual(rider.jar_path, "lib/intellij.rider.branding.jar")
        self.assertEqual(rider.images, ("rider/artwork/release/splash.png", "rider/artwork/release/splash@2x.png"))
        self.assertEqual(rider.cache.folder_prefix, "Rider")
        self.assertEqual(by_name["IntelliJ IDEA"].images, ("idea_logo.png", "idea_logo@2x.png"))
        self.assertEqual(by_name["RubyMine"].jar_path, "lib/product-client.jar")

    def test_android_studio_uses_its_own_cache_location(self):
        (studio,) = ANDROID_PRODUCTS
        self.assertEqual(studio.jar_path, "lib/resources.jar")
        self.assertEqual((studio.cache.vendor_dir, studio.cache.folder_prefix), ("Google", "AndroidStudio"))


if __name__ == "__main__":
    unittest.main()
