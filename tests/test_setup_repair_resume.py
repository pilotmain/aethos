# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from aethos_cli.setup_wizard import clear_setup_state, load_setup_state, save_setup_state


def test_setup_state_save_load(tmp_path, monkeypatch) -> None:
    state_file = tmp_path / ".setup_state.json"
    monkeypatch.setattr("aethos_cli.setup_wizard.SETUP_STATE_FILE", state_file)
    save_setup_state(2, {"kind": "fresh", "repo_root": "/tmp/aethos"})
    raw = load_setup_state()
    assert raw is not None
    assert raw.get("step") == 2
    clear_setup_state()
    assert not state_file.exists()
