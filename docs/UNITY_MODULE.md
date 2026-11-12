# Unity Editor module

Replaces the Unity Editor splash screen. Based on research in `research/UNITY_SPLASH_RESEARCH.md`
(Unity 6000.3.23f1).

## How it works

The splash image is not in a JAR, but in the **Win32 resources of `Editor\Unity.dll`**: two PNGs in `BINARY`
resources (id `120` — 575×575, id `121` — 1150×1150 for HiDPI, language 1033). Therefore, the module uses a
dedicated `toolkit/pe_splash` toolkit rather than `jar_splash`.

| Step | What it does | Where |
|---|---|---|
| Read | Custom PE resource tree parser (no `pefile` dependency), does not read the entire file | `system/pe_resources.py` |
| Write | `BeginUpdateResource` / `UpdateResource` / `EndUpdateResource` via `ctypes`; all or nothing | `system/win32_resources.py` |
| Logic | Image fitting, staging copy, verification, backup, file replacement | `toolkit/pe_splash/operations.py` |
| Discovery | Unity Hub (`editors-v2.json`, `editors.json`, `secondaryInstallPath.json`) and standard folders | `modules/unity/installations.py` |

### Replacement safety

1. The file is opened for writing beforehand: if Unity is running or administrator privileges are missing,
   the user sees the reason immediately (without copying ~80 MB unnecessarily).
2. Modifications are made in a **temporary staging copy** next to `Unity.dll`.
3. The staging copy is verified: all resources remain intact, new PNGs are written byte-for-byte,
   and **no other resources have changed**.
4. Only then is `Unity.dll.custom.backup` created (once; subsequent runs leave it untouched)
   and the staging copy atomically replaces the original (`os.replace`).

Any failure prior to step 4 leaves `Unity.dll` untouched. **Restore originals** restores the file from the backup.

## What the user sees

- Each detected Unity version is a separate target ("Unity 6000.3.23f1", path in description). Newer versions appear first.
- The final target **Other location...** prompts for a folder manually: either the Hub version folder or the folder containing `Unity.exe`.
- Standard actions: **Extract images**, **Replace images**, **Restore originals**.
- Extract saves files as `unity_dll_splash_id120_575x575.png` in `extracted/Unity <version>/`.

## Limitations

- Windows only (writing resources requires the Win32 API). Reading and Extract work on any OS.
- Verified on Unity 6000.3.23f1. If another version lacks `BINARY/120` or `BINARY/121` resources
  or they are not PNGs, the action fails with a clear error without modifying anything.
- Non-square images are center-cropped to a square.
- After replacement, the digital signature of `Unity.dll` (Authenticode) becomes invalid; this does not prevent launch.
- Requires administrator privileges (file is in `Program Files`) and Unity Editor must be closed.
- Updating or reinstalling a version via Unity Hub restores the original `Unity.dll`; replacement must be repeated.

## How it is tested

Tests (`python -m unittest discover -s tests -t .`) do not require Windows: resource writing
is mocked by `tests/pe_fixtures.fake_writer`, which rebuilds a synthetic PE. Tests that read the
real `research/Unity.dll` compare the result byte-for-byte against PNGs from the research and are skipped
if the file is absent. Win32 calls are verified with a mocked `kernel32`; **on actual Windows,
`UpdateResource` should still be verified manually** (see below).

Manual verification on Windows: close Unity → run tool as administrator →
Unity Editor → version → Replace images → launch Unity to check the splash → Restore originals.

## Another version with different splash resource locations

If a Unity version uses different resource IDs, update `PeImageResource` in
`modules/unity/catalog.py`. For another application with PNGs in exe/dll resources, create a module similarly using
`PeSplashProduct` + `PeSplashTarget` from `splashmodify.toolkit.pe_splash`.
