# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from aethos_cli.welcome import print_welcome_screen


def test_welcome_screen_mentions_enterprise_setup(capsys, tmp_path) -> None:
    print_welcome_screen(
        install_dir=tmp_path,
        workspace=tmp_path / "ws",
        llm_summary="hybrid",
        feature_labels=["git"],
        api_base="http://127.0.0.1:8010",
        configuration_only=True,
    )
    out = capsys.readouterr().out
    assert "ENTERPRISE_SETUP.md" in out
    assert "aethos start" in out
    assert "Configuration complete" in out
    assert "installed successfully" not in out.lower() or "configuration complete" in out.lower()
