# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from aethos_cli.setup_conversational import build_existing_config_summary


def test_existing_setup_summary_includes_strategy(tmp_path) -> None:
    (tmp_path / ".env").write_text("AETHOS_ROUTING_MODE=local_only\n", encoding="utf-8")
    lines = build_existing_config_summary(repo_root=tmp_path)
    assert any("Local-first" in line for line in lines)
