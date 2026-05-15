# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Agent / dev pipeline parity surfaces — see docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md §4."""

from __future__ import annotations

from app.services.dev_runtime.service import DEV_PIPELINE_SEQUENCE


def test_dev_pipeline_has_analyze_first() -> None:
    assert DEV_PIPELINE_SEQUENCE[0] == "analyze"
    assert "commit" in DEV_PIPELINE_SEQUENCE
