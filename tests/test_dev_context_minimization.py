"""Phase 38 — dev context truncation."""

from __future__ import annotations

from app.services.dev_runtime.privacy import minimize_dev_context


def test_minimize_truncates_logs_and_diffs() -> None:
    long_log = "L\n" * 5000
    long_diff = "D" * 20000
    out = minimize_dev_context({"log": long_log, "diff": long_diff})
    assert len(out["log"]) <= 8001
    assert len(out["diff"]) <= 12001


def test_minimize_caps_files_list() -> None:
    paths = [f"p{i}" for i in range(300)]
    out = minimize_dev_context({"changed_files": paths})
    assert len(out["changed_files"]) == 100
