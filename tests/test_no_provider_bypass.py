# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 10 — CI guard matches pytest rule for provider isolation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_verify_no_direct_providers_script_passes() -> None:
    root = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [sys.executable, str(root / "scripts" / "verify_no_direct_providers.py")],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr or r.stdout
