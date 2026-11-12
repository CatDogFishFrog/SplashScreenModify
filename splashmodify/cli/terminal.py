"""Raw terminal access: output, line input, width and capability detection."""

import dataclasses
import os
import shutil
import sys
from collections.abc import Callable
from typing import TextIO

from splashmodify.cli.style import ASCII_SYMBOLS, UNICODE_SYMBOLS, Style, Symbols


class QuitRequested(Exception):
    """The user asked to leave the application (``q``, Ctrl+C or end of input)."""


class Console:
    def __init__(
        self,
        *,
        input_func: Callable[[str], str] = input,
        output: TextIO | None = None,
        style: Style | None = None,
        width: int | None = None,
    ) -> None:
        self._input = input_func
        self._output = output if output is not None else sys.stdout
        self.style = style if style is not None else Style()
        self._fixed_width = width

    @classmethod
    def for_terminal(cls) -> "Console":
        """A console on the real stdout with colors and symbols matched to what it supports."""
        stream = sys.stdout
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")  # never crash on an unprintable character in a path
        style = Style(color=_supports_color(stream), symbols=_pick_symbols(stream))
        return cls(output=stream, style=style)

    @property
    def width(self) -> int:
        return self._fixed_width or shutil.get_terminal_size(fallback=(100, 24)).columns

    def print(self, text: str = "") -> None:
        print(text, file=self._output, flush=True)

    def read(self, prompt: str) -> str:
        try:
            return self._input(prompt)
        except (EOFError, KeyboardInterrupt):
            self.print()
            raise QuitRequested from None


def _pick_symbols(stream: TextIO) -> Symbols:
    """Unicode symbols if the stream's encoding can represent them, otherwise ASCII."""
    encoding = getattr(stream, "encoding", None) or "ascii"
    try:
        "".join(dataclasses.astuple(UNICODE_SYMBOLS)).encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return ASCII_SYMBOLS
    return UNICODE_SYMBOLS


def _supports_color(stream: TextIO) -> bool:
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    is_terminal = getattr(stream, "isatty", lambda: False)()
    return bool(is_terminal) and _enable_virtual_terminal()


def _enable_virtual_terminal() -> bool:
    """Turn on ANSI escape processing in the Windows console. Always true elsewhere."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetStdHandle.restype = wintypes.HANDLE
        kernel32.GetStdHandle.argtypes = (wintypes.DWORD,)
        kernel32.GetConsoleMode.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.SetConsoleMode.argtypes = (wintypes.HANDLE, wintypes.DWORD)

        handle = kernel32.GetStdHandle(wintypes.DWORD(-11))  # STD_OUTPUT_HANDLE
        mode = wintypes.DWORD()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except (AttributeError, OSError, ValueError):
        return False
