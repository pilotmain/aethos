# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise setup APIs (Phase 4 Step 10)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from app.services.setup.setup_status import build_setup_status

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status")
def setup_status() -> dict:
    return build_setup_status(repo_root=Path.cwd())
