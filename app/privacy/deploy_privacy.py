# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Deployment result privacy metadata (additive; no orchestration redesign)."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.privacy.pii_detection import detect_pii
from app.privacy.pii_redaction import redact_text
from app.privacy.privacy_policy import current_privacy_mode
from app.privacy.redaction_policy import should_redact_for_external_model


def augment_deployment_result_privacy(result: dict[str, Any], *, settings: Settings | None = None) -> None:
    """Mutate ``result`` in-place with a ``privacy`` block; optionally redact stdout/stderr."""
    s = settings or get_settings()
    mode = current_privacy_mode(s)
    blob = "\n".join(
        str(result.get(k) or "")
        for k in ("command", "stdout", "stderr", "error", "url")
    )[:80_000]
    matches = detect_pii(blob)
    cats = sorted({m.category for m in matches})
    redacted = False
    if cats and should_redact_for_external_model(s):
        for key in ("stdout", "stderr", "error"):
            if isinstance(result.get(key), str) and result[key]:
                nr = redact_text(str(result[key]))
                if nr != result[key]:
                    redacted = True
                    result[key] = nr
    result["privacy"] = {
        "scanned": True,
        "findings": len(matches),
        "pii_categories": cats,
        "redacted": redacted,
        "egress_allowed": True,
        "privacy_mode": mode.value,
    }
