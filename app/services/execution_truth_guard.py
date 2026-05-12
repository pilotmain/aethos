# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Truth gate for claims about real-world external execution (deployments, cloud consoles, etc.).

Chat/composer paths typically only generate text — they must not read as verified infra actions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ExecutionTruthState(str, Enum):
    SIMULATED = "simulated"
    GUIDED = "guided"
    CONNECTED = "connected"
    EXECUTED = "executed"
    VERIFIED = "verified"


@dataclass(frozen=True)
class ExecutionTruthContext:
    """Evidence that a real external side-effect occurred (all required for strong claims)."""

    external_action_performed: bool = False
    authenticated: bool = False
    verification_passed: bool = False


class ExecutionClaimError(RuntimeError):
    """Raised when code tries to assert verified execution without evidence (optional strict mode)."""


def can_claim_real_execution(ctx: ExecutionTruthContext) -> bool:
    return bool(
        ctx.external_action_performed and ctx.authenticated and ctx.verification_passed
    )


# User appears to request changes against hosted infra / deploy pipelines (not local-only dev).
_RE_USER_INFRA_DEPLOY = re.compile(
    r"(?is)"
    r"\b(railway|render\.com|fly\.io|flyctl|heroku|vercel|netlify|cloudflare\s*workers?|"
    r"pulumi|terraform\s+apply|kubectl\s+(apply|rollout)|k8s|kubernetes|eks|gke|aks|"
    r"ecs\s+deploy|lambda\s+deploy|github\s+actions?\s+deploy|argo(cd)?)\b"
    r"|"
    r"\b(redeploy|re-deploy|rolling\s+restart|restart\s+(the\s+)?(worker|service)|"
    r"fix\s+(the\s+)?(railway|prod|production|hosted)\s+(service|worker|deployment))\b"
)

# Reply reads like a completed external remediation (high trust risk if untrue).
_RE_REPLY_INFRA_SUCCESS = re.compile(
    r"(?is)"
    r"\b(i['’]?ve\s+)?(fixed|patched|redeployed|deployed|rolled\s+back|rolled\s+out|"
    r"restarted\s+(the\s+)?(service|worker|deployment))\b"
    r"|"
    r"\b(the\s+)?(service|worker|deployment)\s+is\s+(now\s+)?(healthy|green|running|up)\b"
    r"|"
    r"\b(heartbeat|health\s*check)\s+(returned|shows|is)\s+ok\b"
    r"|"
    r"\b(successfully\s+)?(deployed|redeployed|pushed\s+to\s+production)\b"
    r"|"
    r"\bissue\s+is\s+(now\s+)?resolved\b.*\b(prod|railway|live|deployment)\b"
)

_DISCLAIMER = (
    "**Important:** Nothing in this reply is a verified change to your live cloud project from this "
    "session. I have **not** run your Railway/CLI/API here unless you connected credentials and a "
    "recorded tool run completed. Treat the above as **guidance or simulation** — tell me if you "
    "want step-by-step commands or to connect access safely.\n\n"
)


def user_requests_external_infra_action(user_text: str) -> bool:
    return bool(_RE_USER_INFRA_DEPLOY.search(user_text or ""))


def reply_claims_completed_infra_work(reply_text: str) -> bool:
    return bool(_RE_REPLY_INFRA_SUCCESS.search(reply_text or ""))


def apply_execution_truth_disclaimer(
    user_text: str,
    reply_text: str,
    *,
    guard_enabled: bool = True,
) -> str:
    """
    If the model narrates completed infra work without proof hooks, prepend a clear simulation notice.

    Deterministic and local — no GPU; intended for composer/chat paths that only called an LLM.
    """
    if not guard_enabled:
        return reply_text or ""
    ut = (user_text or "").strip()
    rt = reply_text or ""
    if not ut or not rt.strip():
        return rt
    if not user_requests_external_infra_action(ut):
        return rt
    if not reply_claims_completed_infra_work(rt):
        return rt
    if _DISCLAIMER.strip()[:80] in rt:
        return rt
    return _DISCLAIMER + rt


__all__ = [
    "ExecutionClaimError",
    "ExecutionTruthContext",
    "ExecutionTruthState",
    "apply_execution_truth_disclaimer",
    "can_claim_real_execution",
    "reply_claims_completed_infra_work",
    "user_requests_external_infra_action",
]
