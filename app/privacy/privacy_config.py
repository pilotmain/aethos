# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.privacy.privacy_modes import PrivacyMode
from app.privacy.privacy_policy import current_privacy_mode

if TYPE_CHECKING:
    from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class PrivacyRuntimeConfig:
    mode: PrivacyMode
    audit_enabled: bool
    pii_redaction_enabled: bool
    local_first_enabled: bool
    external_egress_guard_enabled: bool


def load_privacy_runtime_config(settings: Settings) -> PrivacyRuntimeConfig:
    return PrivacyRuntimeConfig(
        mode=current_privacy_mode(settings),
        audit_enabled=bool(getattr(settings, "aethos_privacy_audit_enabled", True)),
        pii_redaction_enabled=bool(getattr(settings, "aethos_pii_redaction_enabled", False)),
        local_first_enabled=bool(getattr(settings, "aethos_local_first_enabled", False)),
        external_egress_guard_enabled=bool(getattr(settings, "aethos_external_egress_guard_enabled", False)),
    )
