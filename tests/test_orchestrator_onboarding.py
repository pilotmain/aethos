# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from aethos_cli.setup_onboarding_profile import load_onboarding_profile, save_onboarding_profile


def test_onboarding_profile_roundtrip(tmp_path, monkeypatch) -> None:
    path = tmp_path / "onboarding_profile.json"
    monkeypatch.setattr("aethos_cli.setup_onboarding_profile.onboarding_profile_path", lambda: path)
    save_onboarding_profile({"display_name": "Alex", "tone": "calm"})
    loaded = load_onboarding_profile()
    assert loaded and loaded.get("display_name") == "Alex"
