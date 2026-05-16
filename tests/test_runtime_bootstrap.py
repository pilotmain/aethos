# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_bootstrap import build_runtime_bootstrap, write_browser_bootstrap


def test_runtime_bootstrap(tmp_path, monkeypatch) -> None:
    boot = tmp_path / "mc_browser_bootstrap.json"
    monkeypatch.setattr("app.services.mission_control.runtime_bootstrap._bootstrap_file", lambda: boot)
    write_browser_bootstrap(api_base="http://127.0.0.1:8000", user_id="u1")
    out = build_runtime_bootstrap(repo_root=tmp_path)
    assert out["runtime_bootstrap"]["seamless_localhost"] is True
