# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.providers.repair.fix_and_redeploy import _brain_operator_line, _evidence_summary


def test_operator_summary_helpers() -> None:
    line = _brain_operator_line({"selected_provider": "deterministic", "selected_model": "m1"})
    assert line == "deterministic/m1"
    ev = _evidence_summary({"failure_category": "build_failure", "workspace_files": ["a"], "package_scripts": {}, "privacy": {}})
    assert ev["failure_category"] == "build_failure"
