"""``nexa config`` — show repo ``.env`` path and optionally open in ``$EDITOR``."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def cmd_config(*, edit: bool = False) -> int:
    env_path = (_repo_root() / ".env").resolve()
    print(f"Nexa environment file:\n  {env_path}\n")
    if not env_path.is_file():
        print("File does not exist yet — run `python -m aethos_cli setup` first.", file=sys.stderr)
        return 1
    editor = (os.environ.get("EDITOR") or "").strip()
    if edit and editor:
        print(f"Launching $EDITOR ({editor})…")
        try:
            subprocess.run([editor, str(env_path)], check=False)
            return 0
        except OSError as exc:
            print(f"Could not launch editor: {exc}", file=sys.stderr)
            return 1
    if edit and not editor:
        print("Set EDITOR (e.g. export EDITOR=nano) to open the file from this command.")
    print("Tip: copy path above or run `nano .env` from the repo root.")
    return 0


__all__ = ["cmd_config"]
