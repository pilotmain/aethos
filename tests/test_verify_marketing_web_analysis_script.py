"""Smoke: verify script CLI and imports (no network)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_verify_marketing_script_help_succeeds() -> None:
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_marketing_web_analysis.py"), "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0
    out = (r.stdout or "") + (r.stderr or "")
    assert "--no-search" in out


def test_verify_marketing_script_importable() -> None:
    import runpy

    ns = runpy.run_path(
        str(ROOT / "scripts" / "verify_marketing_web_analysis.py"),
        run_name="__not_main__",
    )
    assert callable(ns.get("main"))
