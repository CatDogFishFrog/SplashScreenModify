"""Colors and symbols, with plain fallbacks for terminals that cannot show them."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Symbols:
    breadcrumb: str
    success: str
    warning: str
    error: str
    question: str
    ellipsis: str


UNICODE_SYMBOLS = Symbols(breadcrumb="›", success="√", warning="!", error="×", question="?", ellipsis="…")
ASCII_SYMBOLS = Symbols(breadcrumb=">", success="+", warning="!", error="x", question="?", ellipsis="...")


class Style:
    def __init__(self, *, color: bool = False, symbols: Symbols = ASCII_SYMBOLS) -> None:
        self._color = color
        self.symbols = symbols

    def _paint(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self._color else text

    def bold(self, text: str) -> str:
        return self._paint("1", text)

    def dim(self, text: str) -> str:
        return self._paint("90", text)

    def accent(self, text: str) -> str:
        return self._paint("36", text)

    def success(self, text: str) -> str:
        return self._paint("32", text)

    def warning(self, text: str) -> str:
        return self._paint("33", text)

    def error(self, text: str) -> str:
        return self._paint("31", text)
