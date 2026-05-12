# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""GitHub PR webhook + manual review trigger (Phase 23 — automated PR reviews)."""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import get_settings
from app.services.pr_review.orchestrator import PRReviewOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pr-review", tags=["pr-review"])


def _verify_github_signature(secret: str, raw_body: bytes, signature_header: str | None) -> bool:
    if not signature_header:
        return False
    sig = signature_header.strip()
    if sig.startswith("sha256="):
        sig = sig[7:]
    mac = hmac.new(secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256)
    expected = mac.hexdigest()
    try:
        return hmac.compare_digest(expected, sig)
    except Exception:
        return False


async def _require_pr_review_enabled() -> None:
    s = get_settings()
    if not s.nexa_pr_review_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PR review disabled (set NEXA_PR_REVIEW_ENABLED=true)",
        )


async def verify_github_pr_webhook(request: Request) -> bytes:
    """Read raw body; optionally enforce GitHub HMAC (X-Hub-Signature-256)."""
    await _require_pr_review_enabled()
    raw = await request.body()
    s = get_settings()
    secret = (s.nexa_pr_review_webhook_secret or "").strip()
    if not secret:
        return raw
    sig = request.headers.get("x-hub-signature-256") or request.headers.get("X-Hub-Signature-256")
    if not _verify_github_signature(secret, raw, sig):
        logger.warning("pr_review webhook signature verification failed")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid webhook signature")
    return raw


@router.post("/webhook")
async def pr_webhook(
    request: Request,
    raw: bytes = Depends(verify_github_pr_webhook),
) -> dict[str, Any]:
    """Handle GitHub `pull_request` events (opened, synchronize, ready_for_review)."""
    import json

    try:
        body = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid JSON") from exc

    event_type = (request.headers.get("x-github-event") or request.headers.get("X-GitHub-Event") or "").strip()

    if event_type != "pull_request":
        return {"status": "ignored", "reason": "event_type", "event": event_type or None}

    action = str(body.get("action") or "")
    if action not in ("opened", "synchronize", "ready_for_review"):
        return {"status": "ignored", "reason": "action", "action": action}

    pr = body.get("pull_request") or {}
    repo = body.get("repository") or {}
    full_name = str(repo.get("full_name") or "")
    if "/" not in full_name:
        return {"status": "ignored", "reason": "missing_repository"}
    owner, repo_name = full_name.split("/", 1)
    pr_number = pr.get("number")
    if not isinstance(pr_number, int):
        return {"status": "ignored", "reason": "missing_pr_number"}

    orchestrator = PRReviewOrchestrator(owner, repo_name)
    result = await orchestrator.review_pr(pr_number)
    if result.get("error"):
        # Missing token etc. — surface as 503 for operators
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(result.get("error")),
        )
    return {"status": "reviewed", "result": result}


@router.post("/review/{owner}/{repo}/{pr_number}")
async def review_pr_manually(owner: str, repo: str, pr_number: int) -> dict[str, Any]:
    """Manually trigger a PR review (same pipeline as the webhook)."""
    await _require_pr_review_enabled()
    orchestrator = PRReviewOrchestrator(owner, repo)
    result = await orchestrator.review_pr(pr_number)
    if result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(result.get("error")),
        )
    return result
