# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Gateway hook: natural-language provider operations (Phase 2 Step 5)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.gateway.operator_intent_router import try_operator_provider_nl_turn
from app.services.gateway.context import GatewayContext


def try_gateway_provider_operations_turn(
    gctx: GatewayContext,
    raw_message: str,
    db: Session,
) -> dict[str, Any] | None:
    """Run project-scoped provider actions from NL before generic deploy NL."""
    return try_operator_provider_nl_turn(
        user_id=(gctx.user_id or "").strip(),
        raw_message=raw_message,
        db=db,
    )


__all__ = ["try_gateway_provider_operations_turn"]
