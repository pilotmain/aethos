# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 27 — pytest loads SQLite via NEXA_NEXT_LOCAL_SIDECAR (see tests/conftest.py)."""

from __future__ import annotations

import os


def test_tests_force_sidecar_sqlite() -> None:
    assert os.environ.get("NEXA_NEXT_LOCAL_SIDECAR") == "1"
