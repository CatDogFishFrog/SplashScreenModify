# Adding a module

Everything lives in `splashmodify/modules/`. Restart the tool and the module appears in the menu.
If it does not, the startup banner shows why.

## Another IDE with a JAR splash image

Add one line to `modules/jetbrains/catalog.py`:

```python
_ide("Aqua", jar="lib/product.jar", image="artwork/splash.png", cache_prefix="Aqua"),
```

`image` is the entry name inside the JAR; the `@2x` variant is derived automatically.
Use `extract` on the new entry's JAR to find the right names.

## A new family of JAR-based products

1. Create `modules/my_product/catalog.py` describing products with `JarSplashProduct`
   (see `modules/android_studio/catalog.py` for a registry-based locator).
2. Create `modules/my_product/__init__.py`:

```python
from splashmodify.core import Module
from splashmodify.modules.my_product.catalog import PRODUCTS
from splashmodify.toolkit.jar_splash import JarSplashModule


def create_module() -> Module:
    return JarSplashModule(
        module_id="my_product",
        title="My Product",
        description="One line shown in the menu",
        products=PRODUCTS,
    )
```

## A product with images in exe/dll resources

Use `toolkit/pe_splash` (see `modules/unity/` for a complete example):

```python
from splashmodify.toolkit.pe_splash import AskedBinary, PeImageResource, PeSplashProduct, PeSplashTarget

PRODUCT = PeSplashProduct(name="My App", images=(PeImageResource("BINARY", 120),))
target = PeSplashTarget(PRODUCT, AskedBinary("My App folder", ("MyApp.dll",)))
```

Return such targets from your own `Module.targets()`.

## Something different (custom behavior)

Implement the three contracts from `splashmodify.core`. A complete working example is in
[`docs/examples/example_module.py`](examples/example_module.py); copy it into `splashmodify/modules/`.

The essentials:

```python
class MyAction(Action):
    title = "Do the thing"
    parameters = (Parameter(name="source", prompt="Source file", kind=ParameterKind.FILE),)

    def run(self, context, arguments):
        context.ui.info(f"Working on {arguments['source']}")
        ...
        context.ui.success("Done")


class MyTarget(Target):
    title = "My application"
    def actions(self): return (MyAction(),)


class MyModule(Module):
    id = "my_module"
    title = "My module"
    def targets(self): return (MyTarget(),)


def create_module() -> Module:
    return MyModule()
```

## Rules

- Talk to the user only through `context.ui`; never `print` or `input`.
- Raise `ActionError("clear message")` for expected failures, `OperationCancelled` if the user backs out.
- Write output files only under `context.workspace`.
- Import from `splashmodify.core`, `splashmodify.toolkit` and `splashmodify.system`; never from `cli`
  or from another module. `tests/test_architecture.py` checks this.
- If code is useful to several modules, move it to `toolkit/`.
- Name a file or package `_something` to keep it out of discovery (shared helpers inside a module package
  do not need this, because only the top-level entries of `modules/` are scanned).
