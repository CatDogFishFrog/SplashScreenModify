"""Pluggable modules.

Every sub-package (or single ``.py`` file) here that defines ``create_module()`` is
discovered and shown in the menu automatically. Names starting with ``_`` are ignored.
See docs/ADDING_A_MODULE.md.

Modules are registered explicitly so that discovery works reliably inside
frozen (PyInstaller) executables where ``pkgutil.iter_modules`` cannot scan
the PYZ archive.
"""

from splashmodify.modules.android_studio import create_module as _android_studio
from splashmodify.modules.jetbrains import create_module as _jetbrains
from splashmodify.modules.unity import create_module as _unity

MODULE_FACTORIES = (_android_studio, _jetbrains, _unity)
