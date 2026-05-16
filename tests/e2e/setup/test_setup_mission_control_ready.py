# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from aethos_cli.setup_mission_control import seed_mission_control_connection


def test_setup_mission_control_ready(tmp_path: Path) -> None:
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "package.json").write_text('{"name":"mc"}', encoding="utf-8")
    u = seed_mission_control_connection(repo_root=tmp_path, api_base="http://127.0.0.1:8010")
    assert u["API_BASE_URL"] == "http://127.0.0.1:8010"
    assert (tmp_path / "web" / ".env.local").read_text(encoding="utf-8").find("NEXT_PUBLIC") >= 0
