# Architecture

## Goals

- The application core does not know what any module does.
- The console interface is separate from everything else and can be replaced.
- A new module is added by dropping a package into `splashmodify/modules/`; nothing else changes.
- Each file is small and has one reason to change.

## Layers

```
            bootstrap.py   (wires the layers together; the only place that knows all of them)
                 |
      +----------+-----------+
      |                      |
     cli  ------->  core  <-------  modules  --->  toolkit  --->  system
 (console UI)    (contracts)       (plugins)    (shared tools)  (OS adapters)
                                        \________________________/
                                           modules may use both
```

| Package | Responsibility | May import |
|---|---|---|
| `core` | Contracts (`Module`, `Target`, `Action`), user-interface ports, module discovery | standard library only |
| `cli` | Menus, prompts, colors; implements the `core` ports for a console | `core`, `system` |
| `system` | Windows registry, path parsing, well-known folders, PE resource reading and writing | standard library only |
| `toolkit` | Reusable implementations that several modules share (today: JAR splash images, images in exe/dll resources) | `core`, `system`, Pillow |
| `modules` | Plugins; each declares *what* it supports, mostly as data | `core`, `toolkit`, `system` |
| `bootstrap` | Composition root | everything |

These rules are enforced by `tests/test_architecture.py`. A module may also not import another module.

## The contract

The application navigates a tree of three levels and knows nothing more about it:

```
Module  ->  Target  ->  Action
JetBrains IDEs  ->  PyCharm  ->  Replace images
```

- `Module` (`id`, `title`, `description`, `targets()`): a group of related things.
- `Target` (`title`, `description`, `actions()`): one thing that can be worked on.
- `Action` (`title`, `description`, `parameters`, `run(context, arguments)`): one operation.
- `Parameter`: input the application collects before `run`, as text, an existing file, or an existing folder.
- `ActionContext`: the user interface (`ui`) and a `workspace` folder for output files.

`targets()` and `actions()` are methods and `title`/`description` may be properties, so menus reflect current
state. For example, the JetBrains targets show `detected` when the IDE is found on the machine.

### Talking to the user

Modules never print or call `input()`. They use the `UserInterface` port from `core.ui`:

- report: `info`, `success`, `warning`
- ask: `ask_text`, `ask_file`, `ask_directory` (each returns `None` if the user cancels)

The console implements it in `cli/console_ui.py`. Tests use `tests/fakes.py`. A GUI would be another implementation.

### Errors

- `ActionError`: an expected failure; its message is shown as is.
- `OperationCancelled`: the user backed out; shown as "Cancelled."
- Anything else is reported as an unexpected error and the session continues
  (`SPLASHMODIFY_DEBUG=1` adds a traceback).

## Startup flow

1. `bootstrap.main()` asks `core.discover_modules` to scan `splashmodify.modules`.
2. Every sub-package or file there that defines `create_module()` is imported and instantiated.
   Names starting with `_` are skipped. A module that fails to load, or reuses an id, is reported in the
   banner and does not affect the others.
3. `cli.ConsoleApp` shows a menu over the loaded modules. Levels with one choice are skipped, so a module
   with one target (Android Studio) goes straight to its actions.

## The JAR splash toolkit

JetBrains IDEs and Android Studio work the same way: images inside a JAR, a backup, a cache to clear.
`toolkit/jar_splash` implements that once:

- `JarSplashProduct`: a declarative description (name, JAR, image entries, how to find the installation, cache).
- `JarSplashModule`: turns a list of products into a module with extract / replace / restore actions.
- `archive.py`: JAR and image operations that do no console I/O and return results.
- `locators.py`: strategies for finding an installation (user environment variable, registry value).
- `installation.py`: detect, otherwise ask the user.

A product catalog is plain Python (`modules/<name>/catalog.py`), so it is type-checked and needs no data
files in the executable.

## The PE splash toolkit

Applications that keep images in the resources of an executable (Unity Editor: `Editor/Unity.dll`) use
`toolkit/pe_splash`: `PeSplashProduct` describes the image resources, `PeSplashTarget` gives one installed
copy the extract / replace / restore actions. Unlike JAR products, a module may build its targets dynamically
(one per detected installation), see `modules/unity`. Reading is pure Python (`system/pe_resources.py`);
writing goes through the Win32 API (`system/win32_resources.py`) and is injectable for tests.
The replacement is done on a temporary copy, verified, and only then swapped in. See [UNITY_MODULE.md](UNITY_MODULE.md).

## Design decisions

- **Convention over registration.** `create_module()` is an explicit factory, so importing a helper class is
  never mistaken for a module.
- **Failure isolation at the plugin boundary.** Discovery is the one place that catches broad exceptions.
- **Ports instead of imports.** Modules depend on `core.ui` protocols, never on the console.
- **No third-party UI library.** Numbered menus with name matching work in any terminal and add nothing to the
  executable; colors and Unicode symbols fall back to plain text when unsupported (`NO_COLOR` is honored).
- **Pure functions where possible.** `archive.py`, `cache.py` and `interpret_input` are tested without any I/O mocking.
