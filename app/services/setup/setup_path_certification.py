# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""One-curl enterprise path certification (Phase 4 Step 11)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

CERTIFIED_FLOW = [
    "curl | bash",
    "install.sh (clone or update ~/.aethos)",
    "scripts/setup.sh (thin bootstrap)",
    "aethos setup (enterprise wizard)",
    "aethos_cli.setup_enterprise.run_enterprise_setup_extensions",
    "seed_mission_control_connection",
    "run_setup_health_checks",
    "print_setup_final_summary",
]


def certify_one_curl_path(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    install_sh = root / "install.sh"
    setup_sh = root / "scripts" / "setup.sh"
    setup_py = root / "scripts" / "setup.py"
    wizard = root / "aethos_cli" / "setup_wizard.py"
    enterprise = root / "aethos_cli" / "setup_enterprise.py"
    checks = {
        "install_sh_exists": install_sh.is_file(),
        "install_routes_setup_sh": install_sh.is_file() and "scripts/setup.sh" in install_sh.read_text(encoding="utf-8"),
        "setup_sh_routes_aethos_setup": setup_sh.is_file() and "aethos" in setup_sh.read_text(encoding="utf-8"),
        "setup_py_is_shim": setup_py.is_file() and "_delegate_to_aethos_setup" in setup_py.read_text(encoding="utf-8"),
        "setup_wizard_exists": wizard.is_file(),
        "enterprise_extensions_exists": enterprise.is_file(),
        "wizard_calls_enterprise": wizard.is_file() and "run_enterprise_setup_extensions" in wizard.read_text(encoding="utf-8"),
        "canonical_module": (root / "app" / "services" / "setup" / "canonical_install_path.py").is_file(),
    }
    certified = all(checks.values())
    return {
        "certified": certified,
        "flow": CERTIFIED_FLOW,
        "checks": checks,
        "enterprise_default": True,
    }
