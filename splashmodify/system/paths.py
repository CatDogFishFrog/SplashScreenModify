"""Parsing of paths typed or pasted by a user."""

import os
from pathlib import Path


def parse_user_path(value: str | Path) -> Path:
    """Turn user input into a ``Path``.

    Surrounding quotes (added by drag-and-drop or "Copy as path") are removed,
    and ``~`` and environment variables are expanded.
    """
    text = str(value).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        text = text[1:-1].strip()
    if not text:
        raise ValueError("Path cannot be empty.")
    return Path(os.path.expandvars(os.path.expanduser(text)))
