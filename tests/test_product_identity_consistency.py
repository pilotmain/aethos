# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.core import product_identity


def test_canonical_terms_present() -> None:
    terms = product_identity.TERMS
    assert terms["orchestrator"] == "AethOS Orchestrator"
    assert terms["mission_control"] == "Mission Control"
    assert terms["runtime_workers"] == "Runtime Workers"
    assert terms["marketplace_plugins"] == "Runtime Plugins"
    assert terms["skill_marketplace"] == "Skill Marketplace"
