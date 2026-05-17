# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from aethos_cli.setup_conversational import build_existing_config_summary


def test_existing_config_summary_reads_env(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "\n".join(
            [
                "AETHOS_ROUTING_MODE=hybrid",
                "AETHOS_ROUTING_PREFERENCE=balanced",
                "ANTHROPIC_API_KEY=sk-test",
                "NEXA_WORKSPACE_ROOT=/tmp/ws",
                "AETHOS_WEB_API_TOKEN=abc",
            ]
        ),
        encoding="utf-8",
    )
    lines = build_existing_config_summary(repo_root=tmp_path)
    text = "\n".join(lines)
    assert "Hybrid" in text or "hybrid" in text.lower()
    assert "Anthropic" in text
    assert "/tmp/ws" in text
    assert "Mission Control: configured" in text
