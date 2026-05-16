# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import shutil

from app.providers.provider_registry import get_provider_spec


def detect_cli_path(provider_id: str) -> str | None:
    spec = get_provider_spec(provider_id)
    if not spec:
        return None
    bin_name = str(spec.get("binary") or "").strip()
    if not bin_name:
        return None
    return shutil.which(bin_name)
