"""Backup / restore helpers for setup override flows."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


def backup_env_file(env_path: Path, backups_dir: Path | None = None) -> Path:
    """
    Copy ``.env`` to a timestamped backup next to the file (or under ``backups_dir``).

    Returns the path to the backup file.
    """
    if not env_path.is_file():
        raise FileNotFoundError(env_path)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = backups_dir or env_path.parent
    base.mkdir(parents=True, exist_ok=True)
    dest = base / f"{env_path.name}.backup.{stamp}"
    shutil.copy2(env_path, dest)
    return dest
