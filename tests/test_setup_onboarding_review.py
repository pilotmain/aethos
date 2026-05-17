# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

from aethos_cli.setup_onboarding_profile import load_onboarding_profile, onboarding_profile_path


def test_load_onboarding_profile_when_present(tmp_path: Path, monkeypatch) -> None:
    prof_dir = tmp_path / ".aethos"
    prof_dir.mkdir()
    path = prof_dir / "onboarding_profile.json"
    path.write_text(json.dumps({"v": 1, "profile": {"display_name": "Alex", "tone": "concise"}}), encoding="utf-8")
    monkeypatch.setattr("aethos_cli.setup_onboarding_profile.onboarding_profile_path", lambda: path)
    loaded = load_onboarding_profile()
    assert loaded is not None
    assert loaded.get("display_name") == "Alex"


def test_onboarding_profile_path_under_aethos() -> None:
    assert onboarding_profile_path().name == "onboarding_profile.json"
