# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from aethos_cli.setup_progress_state import build_progress_status, load_setup_progress, mark_section, save_setup_progress


def test_setup_progress_state(tmp_path, monkeypatch) -> None:
    pfile = tmp_path / "setup_progress.json"
    monkeypatch.setattr("aethos_cli.setup_progress_state.PROGRESS_FILE", pfile)
    mark_section("welcome", completed=True)
    save_setup_progress(runtime_strategy="hybrid")
    st = build_progress_status()
    assert "welcome" in st["completed_sections"]
    assert load_setup_progress().get("runtime_strategy") == "hybrid"
