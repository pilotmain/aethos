# SPDX-License-Identifier: Apache-2.0

from pathlib import Path


def test_mission_control_bootstrap_module_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    mod = root / "aethos_cli" / "setup_mission_control.py"
    text = mod.read_text(encoding="utf-8")
    assert "seed_mission_control" in text
    assert ".env.local" in text or "env.local" in text
