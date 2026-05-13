# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Update a single ``KEY=value`` line in the repo-root ``.env`` file (best-effort, dev / operator)."""

from __future__ import annotations

from pathlib import Path

from app.core.config import ENV_FILE_PATH


def update_repo_env_key(key: str, value: str, *, env_path: Path | None = None) -> None:
    """Upsert ``key`` in ``.env`` (creates the file if missing)."""
    path = env_path or ENV_FILE_PATH
    k = (key or "").strip()
    if not k:
        return
    lines: list[str] = []
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines()
    updated = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        ek, _, _ = line.partition("=")
        if ek.strip() == k:
            lines[i] = f"{k}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{k}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
