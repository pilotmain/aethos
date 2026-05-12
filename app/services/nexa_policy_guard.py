# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Shared enforcement for privileged execution — call at every trust boundary (host, tools, orchestration hooks).

Does not replace DB permission checks; adds policy + provenance invariants.

Call ``enforce_nexa_privileged_policy`` (or wrappers) before executing work from:

- Host executor / local tools
- Future unified tool runners and agent action abstractions
- Webhooks that deserialize into execution payloads
- Background jobs that reconstruct payloads from queue rows

Skipping this guard reintroduces prompt-only safety and spoofable provenance.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings
from app.services.content_provenance import (
    apply_trusted_instruction_source,
    enforce_instruction_source_for_host,
)
from app.services.nexa_safety_policy import (
    PolicyDowngradeError,
    stamp_host_payload,
    verify_payload_policy,
)
from app.services.sensitivity import stamp_payload_sensitivity

logger = logging.getLogger(__name__)


def enforce_nexa_privileged_policy(
    payload: dict[str, Any] | None,
    *,
    trusted_instruction_source: str | None = None,
    boundary: str = "host",
) -> dict[str, Any]:
    """
    Verify immutable policy + instruction provenance before privileged local execution.

    When ``trusted_instruction_source`` is set (e.g. chat NL path), it **overwrites** any
    client-supplied ``instruction_source`` — never trust LLM / external JSON alone.

    ``boundary`` is for logs only (host / orchestrator / worker / internal).
    """
    p = dict(payload or {})
    if trusted_instruction_source is not None:
        p = apply_trusted_instruction_source(p, trusted_instruction_source)
    p = stamp_host_payload(p)
    p = stamp_payload_sensitivity(p)
    enforce_instruction_source_for_host(p)
    ok, detail = verify_payload_policy(p)
    s = get_settings()
    strict = bool(getattr(s, "nexa_safety_policy_strict", False))
    if not ok:
        low = (detail or "").lower()
        if strict and "downgrade" in low:
            logger.warning(
                "nexa_policy_guard boundary=%s downgrade_blocked detail=%s", boundary, detail[:300]
            )
            raise PolicyDowngradeError(detail or "policy downgrade blocked")
        if strict:
            logger.warning("nexa_policy_guard boundary=%s strict_fail detail=%s", boundary, detail[:400])
            raise ValueError(detail or "safety policy verification failed")
        logger.warning(
            "nexa_policy_guard boundary=%s policy_drift detail=%s", boundary, (detail or "")[:400]
        )
    logger.info(
        "safety.enforcement.path boundary=%s action_type=nexa_privileged_policy ok=%s sensitivity=%s",
        boundary,
        ok,
        p.get("_nexa_sensitivity"),
    )
    return p
