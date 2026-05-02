"""Phase 44C — dev failure classification and strategy hints on run results."""

from __future__ import annotations

from app.services.dev_runtime.failure_intel import classify_dev_failure, select_fix_strategy


def test_classify_privacy_blocked() -> None:
    fc = classify_dev_failure(error_text="x", tests_passed=False, adapter_round_ok=True, privacy_blocked=True)
    assert fc == "privacy_blocked"
    assert select_fix_strategy(fc) == "relax_scope_or_privacy_gate"


def test_classify_test_failure() -> None:
    fc = classify_dev_failure(error_text=None, tests_passed=False, adapter_round_ok=True, privacy_blocked=False)
    assert fc == "test_failure"


def test_classify_adapter_error() -> None:
    fc = classify_dev_failure(error_text=None, tests_passed=False, adapter_round_ok=False, privacy_blocked=False)
    assert fc == "adapter_error"


def test_success_classification() -> None:
    fc = classify_dev_failure(error_text=None, tests_passed=True, adapter_round_ok=True, privacy_blocked=False)
    assert fc == "none"
