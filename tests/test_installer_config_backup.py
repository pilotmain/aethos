# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from scripts.setup_helpers.backup import backup_env_file


def test_backup_env_file_timestamped(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("KEY=value\n", encoding="utf-8")
    dest = backup_env_file(env, backups_dir=tmp_path / "backups")
    assert dest.is_file()
    assert ".backup." in dest.name
