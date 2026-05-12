# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Subscription tier gate for FastAPI routes (Phase 51 cloud)."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.api.deps.cloud_saas import CloudSaasContext, get_cloud_saas_context
from app.services.cloud_saas.billing_features import tier_at_least


class RequireCloudTier:
    """Usage: ``Depends(RequireCloudTier(\"business\"))``."""

    def __init__(self, min_tier: str) -> None:
        self.min_tier = (min_tier or "free").strip().lower()

    async def __call__(self, ctx: CloudSaasContext = Depends(get_cloud_saas_context)) -> CloudSaasContext:
        current = (ctx.billing.subscription_tier or "free").strip().lower()
        if not tier_at_least(current, self.min_tier):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Upgrade to {self.min_tier} or higher to access this feature",
            )
        return ctx


__all__ = ["RequireCloudTier"]
