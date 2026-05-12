# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Merge Railway / Vercel token env vars for CLI subprocesses (explicit inheritance)."""

from __future__ import annotations

import os


def cli_auth_env() -> dict[str, str]:
    """Copy process env and ensure CLI tokens are set when present in the environment."""
    env = os.environ.copy()
    rt = (os.environ.get("RAILWAY_TOKEN") or os.environ.get("RAILWAY_API_TOKEN") or "").strip()
    if rt:
        env["RAILWAY_TOKEN"] = rt
    vt = (os.environ.get("VERCEL_TOKEN") or os.environ.get("VERCEL_API_TOKEN") or "").strip()
    if vt:
        env["VERCEL_TOKEN"] = vt
    return env


__all__ = ["cli_auth_env"]
