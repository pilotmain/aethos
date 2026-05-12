# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""User-facing privacy mode (Phase 19) — normalize env / settings values."""

from __future__ import annotations

from typing import Any, Literal

UserPrivacyMode = Literal["standard", "strict", "paranoid"]


def normalize_user_privacy_mode(raw: Any) -> UserPrivacyMode:
    x = str(raw or "standard").strip().lower()
    if x in ("standard", "strict", "paranoid"):
        return x  # type: ignore[return-value]
    return "standard"
