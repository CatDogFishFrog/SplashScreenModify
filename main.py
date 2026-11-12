"""Launcher for running from source and the entry point for PyInstaller builds."""

from splashmodify.bootstrap import main

if __name__ == "__main__":
    raise SystemExit(main())
