# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from aethos_cli.setup_mission_control import seed_mission_control_connection


def test_seed_mission_control_connection(tmp_path: Path) -> None:
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "package.json").write_text("{}", encoding="utf-8")
    updates = seed_mission_control_connection(repo_root=tmp_path, api_base="http://127.0.0.1:8010")
    assert updates.get("NEXA_WEB_API_TOKEN")
    assert updates.get("TEST_X_USER_ID")
    assert (tmp_path / "web" / ".env.local").is_file()
