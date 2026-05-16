# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path


def test_install_sh_execs_setup_sh() -> None:
    text = Path("install.sh").read_text(encoding="utf-8")
    assert "scripts/setup.sh" in text
    assert "AethOS" in text
