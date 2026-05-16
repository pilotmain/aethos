# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Final UI branding purge scan (Phase 4 Step 12)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

USER_FACING_NEXA_PATTERNS = ("Nexa ", " Nexa", "Nexa's", "the Nexa", "Open Nexa", "Back to Nexa")

ALLOWED_NEXA_PATHS = (
    "web/lib/config.ts",
    "web/lib/webUserId.ts",
    "web/lib/api/governance.ts",
    "web/lib/api/marketplace.ts",
    "web/lib/mission-control/eventsWsUrl.ts",
    "web/components/mission-control/Phase22Overview.tsx",
)


def scan_ui_branding_final(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    web = root / "web"
    violations: list[dict[str, str]] = []
    for path in web.rglob("*"):
        if not path.is_file() or path.suffix not in (".tsx", ".ts"):
            continue
        rel = str(path.relative_to(root))
        if any(rel.startswith(p) for p in ALLOWED_NEXA_PATHS):
            continue
        if "differentiators" in rel or rel.endswith("navigation.ts"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pat in USER_FACING_NEXA_PATTERNS:
            if pat in text:
                violations.append({"path": rel, "pattern": pat.strip()})
        for term in ("ClawHub", "OpenHub"):
            if term in text and "clawhub/" not in text.lower():
                violations.append({"path": rel, "pattern": term})
    from app.services.setup.branding_purge import scan_user_facing_branding

    base = scan_user_facing_branding(repo_root=root)
    return {
        "clean": len(violations) == 0 and base.get("clean"),
        "nexa_ui_violations": violations[:60],
        "legacy_scan": base,
        "phase": "phase4_step12",
    }
