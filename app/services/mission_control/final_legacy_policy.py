# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Final legacy reference policy (Phase 4 Step 13)."""

from __future__ import annotations

from typing import Any

from app.services.setup.branding_purge import scan_user_facing_branding
from app.services.setup.ui_branding_purge_final import scan_ui_branding_final


def build_final_legacy_policy(*, repo_root=None) -> dict[str, Any]:
    from pathlib import Path

    root = repo_root or Path.cwd()
    return {
        "final_legacy_policy": {
            "user_facing_brand": "AethOS",
            "nexa_allowed": ["NEXA_* env aliases", "migration internals", "compatibility tests"],
            "openclaw_allowed": ["README inspiration", "docs/OPENCLAW_*", "tests/test_openclaw_*"],
        },
        "compatibility_alias_policy": {
            "AETHOS_API_URL": "NEXA_API_BASE",
            "AETHOS_API_BEARER": "NEXA_WEB_API_TOKEN",
            "AETHOS_USER_ID": "TEST_X_USER_ID / X_USER_ID",
            "note": "Aliases remain for backward compatibility only",
        },
        "branding_scans": {
            "cli": scan_user_facing_branding(repo_root=root),
            "ui": scan_ui_branding_final(repo_root=root),
        },
    }
