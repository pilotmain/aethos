# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

from aethos_cli.setup_onboarding_profile import load_onboarding_profile, onboarding_profile_path, save_onboarding_profile


def test_save_and_load_onboarding_profile(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "aethos_cli.setup_onboarding_profile.onboarding_profile_path",
        lambda: tmp_path / "onboarding_profile.json",
    )
    save_onboarding_profile({"display_name": "Alex", "tone": "concise"})
    loaded = load_onboarding_profile()
    assert loaded is not None
    assert loaded.get("display_name") == "Alex"
