"""Write/backup primitives for sync operations."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


def backup_file(path: Path, backup_root: Path) -> Path:
    """Create a backup copy of path under backup_root."""
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_path = backup_root / path.name
    shutil.copy2(path, backup_path)
    return backup_path


def atomic_write(path: Path, content: str) -> None:
    """Write content atomically via temp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as tmp:
        tmp.write(content)
        tmp_name = tmp.name
    os.replace(tmp_name, path)
