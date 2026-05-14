# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Expose setup-time credentials for Mission Control (loopback-only; live merge from repo ``.env``)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.setup_creds_file import read_setup_creds_merged_dict

router = APIRouter(tags=["setup"])


def _client_loopback(request: Request) -> bool:
    c = request.client
    if c is None:
        return True
    host = (c.host or "").strip()
    # Starlette TestClient uses host "testclient".
    if host == "testclient":
        return True
    return host in ("127.0.0.1", "::1", "localhost", "::ffff:127.0.0.1")


@router.get("/api/setup-creds")
async def get_setup_creds(request: Request) -> dict[str, str]:
    if not _client_loopback(request):
        return {}
    return read_setup_creds_merged_dict()
