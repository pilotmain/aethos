# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from aethos_cli.setup_mission_control import seed_mission_control_connection


def test_setup_connection_seed_keys(tmp_path: Path) -> None:
    updates = seed_mission_control_connection(repo_root=tmp_path, api_base="http://127.0.0.1:8010", user_id="u1", bearer_token="tok")
    assert updates.get("NEXA_WEB_API_TOKEN") == "tok"
    assert updates.get("AETHOS_API_BEARER") == "tok"
    assert updates.get("AETHOS_USER_ID") == "u1"
    assert "NEXA_WEB_ORIGINS" in updates
