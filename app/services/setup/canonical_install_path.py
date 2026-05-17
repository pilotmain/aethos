# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Canonical public installer path — install.sh → setup.sh → aethos setup."""

from __future__ import annotations

from pathlib import Path
from typing import Any

PUBLIC_INSTALL_COMMAND = (
    "curl -fsSL https://raw.githubusercontent.com/pilotmain/aethos/main/install.sh | bash"
)

CANONICAL_FLOW = [
    "install.sh (public)",
    "scripts/setup.sh (thin bootstrap)",
    "aethos setup (enterprise wizard)",
    "aethos_cli/setup_enterprise.py",
    "aethos_cli/setup_mission_control.py",
    "runtime validation + ready-state",
]

DEPRECATED_PATHS = [
    "scripts/setup.py direct UX (legacy; shim only)",
    "Numbered-only wizard without enterprise extensions",
]

INTERNAL_ONLY = [
    "scripts/setup.py --legacy-wizard",
    "AETHOS_SETUP_DRY_RUN=1",
]


def build_canonical_install_path(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    install_sh = root / "install.sh"
    setup_sh = root / "scripts" / "setup.sh"
    setup_py = root / "scripts" / "setup.py"
    wizard = root / "aethos_cli" / "setup_wizard.py"
    text_sh = setup_sh.read_text(encoding="utf-8") if setup_sh.is_file() else ""
    text_py = setup_py.read_text(encoding="utf-8") if setup_py.is_file() else ""
    checks = {
        "install_sh_exists": install_sh.is_file(),
        "install_delegates_setup_sh": "scripts/setup.sh" in (install_sh.read_text(encoding="utf-8") if install_sh.is_file() else ""),
        "setup_sh_delegates_aethos_setup": "aethos_cli" in text_sh and "setup" in text_sh,
        "setup_py_is_shim": "aethos_cli" in text_py and ("__main__" in text_py or "run_setup_wizard" in text_py),
        "enterprise_wizard_exists": wizard.is_file(),
    }
    return {
        "canonical_install_path": {
            "public_command": PUBLIC_INSTALL_COMMAND,
            "canonical_flow": CANONICAL_FLOW,
            "deprecated": DEPRECATED_PATHS,
            "internal_only": INTERNAL_ONLY,
            "local_recovery_command": "bash scripts/setup.sh",
            "checks": checks,
            "locked": all(checks.values()),
            "phase": "canonical_installer_lock",
            "bounded": True,
        }
    }
