"""Допоміжні операції з файлами."""

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def temporary_sibling(file: Path) -> Iterator[Path]:
    """Тимчасовий файл поруч із ``file`` (той самий том, тож ``os.replace`` атомарний); видаляється наприкінці."""
    descriptor, name = tempfile.mkstemp(prefix=f".{file.name}.", suffix=".tmp", dir=file.parent)
    os.close(descriptor)
    path = Path(name)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)
