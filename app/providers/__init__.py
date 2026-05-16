# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 2 Step 3 — local provider CLI intelligence (additive; no new deploy architecture)."""

from __future__ import annotations

from app.providers.intelligence_service import scan_providers_inventory
from app.providers.provider_registry import PROVIDER_IDS, get_provider_spec

__all__ = ["PROVIDER_IDS", "get_provider_spec", "scan_providers_inventory"]
