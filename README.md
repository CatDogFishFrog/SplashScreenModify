# SplashScreenModify

[![CI](https://github.com/CatDogFishFrog/SplashScreenModify/actions/workflows/ci.yml/badge.svg)](https://github.com/CatDogFishFrog/SplashScreenModify/actions/workflows/ci.yml)

> [!NOTE]
> Windows only.

A console tool that replaces splash screens and other branding images of installed applications.
It is built from pluggable modules: JetBrains IDEs, Android Studio and Unity Editor are included, and new
modules are picked up automatically.

## Download

- Release: [SplashScreenModify.exe](https://github.com/CatDogFishFrog/SplashScreenModify/releases/latest/download/SplashScreenModify.exe). All versions are on the [releases](https://github.com/CatDogFishFrog/SplashScreenModify/releases) page.
- Development build of `main`: [SplashScreenModify.zip](https://nightly.link/CatDogFishFrog/SplashScreenModify/workflows/ci/main/SplashScreenModify.zip). It comes from the newest commit that passed the tests and may be unstable.

## Usage

1. Prepare the replacement image (place it anywhere and note its path).
2. Run `python main.py` or the executable from the [releases](https://github.com/CatDogFishFrog/SplashScreenModify/releases) page.
3. Pick a module, an application and an action. You can type a number or part of a name (`py` selects PyCharm),
   `0` goes back and `q` quits.
   - **Extract images** saves the current images to `extracted/<application>/` next to the tool.
   - **Replace images** asks for the picture path (quotes are accepted) and fits it to each original size.
   - **Restore originals** puts the original images back from the backup.
4. If the installation is not detected automatically, you are asked for its root folder (a `bin` folder is accepted).
   For Unity Editor every installed version is listed (found through Unity Hub); choose **Other location...** to type a folder.

Applications detected on this PC are marked `detected` in the list.

## Python environment

Python 3.12 or newer (developed on 3.14).

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python .\main.py
```

## Tests

```powershell
python -m unittest discover -s tests -t .
```

CI runs the same command on Windows with Python 3.12 and 3.14 for every push.

## Build the executable

```powershell
python -m pip install pyinstaller
pyinstaller SplashScreenModify.spec
```

## Project layout

```
main.py                  launcher (also the PyInstaller entry point)
splashmodify/
  core/                  contracts, ports, module discovery (pure Python)
  cli/                   console interface
  system/                registry, paths, well-known folders
  toolkit/jar_splash/    reusable building blocks for JAR-based splash images
  toolkit/pe_splash/     reusable building blocks for images stored in exe/dll resources
  modules/               plugins: jetbrains/, android_studio/, unity/, ...
  bootstrap.py           wires everything together
tests/
docs/
```

- Architecture and the dependency rules: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Adding a module or another IDE: [docs/ADDING_A_MODULE.md](docs/ADDING_A_MODULE.md)
- Unity Editor module (how it works, safety, limits): [docs/UNITY_MODULE.md](docs/UNITY_MODULE.md)
- CI, nightly builds and how to make a release: [docs/RELEASING.md](docs/RELEASING.md)
- Commit message format (it feeds the release notes): [docs/COMMITS.md](docs/COMMITS.md)

## Notes

- If the image's aspect ratio differs from the original, it is center-cropped.
- Administrator privileges may be required to modify files in the installation folder. Close the application before replacing or restoring files.
- A `*.custom.backup` file is created before the first replacement. Later replacements do not overwrite it; **Restore originals** uses it.
- The installation path may not be detected automatically if the IDE was installed through Toolbox.
- Unity Editor: the splash is stored in `Editor\Unity.dll`; close Unity first and run the tool as administrator. The original is kept in `Unity.dll.custom.backup`.
- Set `SPLASHMODIFY_DEBUG=1` to print full tracebacks for unexpected errors.
