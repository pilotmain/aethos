# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path


def test_setup_enterprise_defers_onboarding(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NEXA_NONINTERACTIVE", "1")
    state = tmp_path / ".aethos"
    state.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))

    from aethos_cli.setup_enterprise import run_enterprise_setup_extensions

    bag: dict = {}
    updates: dict = {}
    run_enterprise_setup_extensions(
        repo_root=tmp_path,
        updates=updates,
        api_base="http://127.0.0.1:8010",
        bag=bag,
    )
    assert bag.get("onboarding_deferred") is True
    assert (state / "first_run_onboarding.json").is_file()


def test_needs_first_run_after_deferral(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    from app.services.setup.first_run_operator_onboarding import (
        mark_onboarding_deferred_from_setup,
        needs_first_run_operator_onboarding,
    )

    mark_onboarding_deferred_from_setup()
    assert needs_first_run_operator_onboarding() is True
