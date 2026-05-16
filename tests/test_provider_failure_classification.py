# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.providers.repair.failure_classification import classify_failure_text, diagnose_failure


def test_classify_dependency_failure() -> None:
    assert classify_failure_text("npm ERR! Cannot find module 'left-pad'") == "dependency_failure"


def test_diagnose_missing_package_json() -> None:
    d = diagnose_failure(logs_preview="", workspace_signals=[".git"])
    assert d["failure_category"] == "missing_package_json"
