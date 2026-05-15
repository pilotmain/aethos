# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Deployment NL / intent parity — see docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md §9."""

from __future__ import annotations

from app.services.host_executor_intent import parse_deploy_intent


def test_parse_deploy_intent_bare_deploy() -> None:
    got = parse_deploy_intent("deploy")
    assert got is not None
    assert got.get("intent") == "deploy"
