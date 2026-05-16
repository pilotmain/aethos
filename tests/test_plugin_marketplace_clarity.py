# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from pathlib import Path

from app.services.mission_control.runtime_truth import build_runtime_truth


def test_truth_separates_plugins_and_marketplace() -> None:
    truth = build_runtime_truth(user_id=None)
    assert truth.get("plugins") is not None
    assert truth.get("marketplace") is not None
    assert truth["plugins"] is not truth["marketplace"]


def test_docs_describe_plugin_vs_skill_split() -> None:
    doc = (Path(__file__).resolve().parents[1] / "docs/PLUGIN_VS_SKILL_ARCHITECTURE.md").read_text()
    assert "Runtime plugins" in doc
    assert "Skills" in doc
    assert "operational" in doc.lower()
