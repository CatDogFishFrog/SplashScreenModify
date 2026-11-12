# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

# Modules are discovered at runtime, so PyInstaller cannot see them in the import graph.
# Collecting every submodule of the modules package bundles all of them into the executable.
hidden_imports = collect_submodules('splashmodify.modules')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'unittest', 'test', 'tests', 'tkinter', '_tkinter',
        'email', 'html', 'http', 'xml', 'xmlrpc', 'pydoc',
        'doctest', 'difflib',
        'multiprocessing', 'ssl', 'ftplib', 'smtplib',
        'imaplib', 'poplib', 'nntplib', 'telnetlib',
        'socketserver', 'asyncio', 'concurrent',
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [('O', None, 'OPTION'), ('O', None, 'OPTION')],
    name='JetBrainsSplashModify',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
