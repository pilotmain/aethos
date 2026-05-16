# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Bounded HTTP client helpers for e2e tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def get_bounded(client: TestClient, path: str, *, headers: dict | None = None, timeout: float = 15.0) -> Any:
    return client.get(path, headers=headers or {}, timeout=timeout)
