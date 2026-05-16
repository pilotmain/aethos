# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise setup APIs (Phase 4 Step 10)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from app.services.setup.env_completeness import build_env_completeness_audit
from app.services.setup.mission_control_ready_state import build_mission_control_ready_state
from app.services.setup.setup_path_certification import certify_one_curl_path
from app.services.setup.setup_ready_state_lock import build_setup_ready_state_lock
from app.services.setup.setup_status import build_setup_status

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status")
def setup_status() -> dict:
    return build_setup_status(repo_root=Path.cwd())


@router.get("/ready-state")
def setup_ready_state() -> dict:
    return build_mission_control_ready_state(repo_root=Path.cwd())


@router.get("/certify")
def setup_certify() -> dict:
    return build_setup_ready_state_lock(repo_root=Path.cwd())


@router.get("/env-audit")
def setup_env_audit() -> dict:
    return build_env_completeness_audit(repo_root=Path.cwd())


@router.get("/one-curl")
def setup_one_curl() -> dict:
    return certify_one_curl_path(repo_root=Path.cwd())
