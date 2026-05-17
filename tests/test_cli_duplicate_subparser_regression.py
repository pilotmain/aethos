# SPDX-License-Identifier: Apache-2.0

import subprocess
import sys
from pathlib import Path


def test_aethos_runtime_help_no_duplicate_subparser() -> None:
    """Regression: ``aethos runtime`` must build without ArgumentError."""
    root = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [sys.executable, "-m", "aethos_cli", "runtime", "-h"],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, (r.stderr or r.stdout)[:2000]
    assert "conflicting subparser" not in (r.stderr or "").lower()


def test_aethos_doctor_runs() -> None:
    root = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [sys.executable, "-m", "aethos_cli", "setup", "doctor"],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=60,
        env={**__import__("os").environ, "NEXA_NONINTERACTIVE": "1"},
    )
    assert r.returncode in (0, 1)
    assert "conflicting subparser" not in (r.stderr or "").lower()
