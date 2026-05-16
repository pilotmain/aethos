# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Top-level runtime capability discovery (Phase 4 Step 6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import get_valid_web_user_id
from app.services.mission_control.runtime_api_capabilities import build_runtime_capabilities

router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/capabilities")
def runtime_capabilities(_: str = Depends(get_valid_web_user_id)) -> dict:
    return build_runtime_capabilities()
