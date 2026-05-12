# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Execution truth — programmatic gate requires all evidence flags."""

from __future__ import annotations

import pytest

from app.services.execution_truth_guard import (
    ExecutionClaimError,
    ExecutionTruthContext,
    can_claim_real_execution,
)


def test_cannot_claim_without_all_evidence() -> None:
    assert not can_claim_real_execution(ExecutionTruthContext())
    assert not can_claim_real_execution(
        ExecutionTruthContext(external_action_performed=True, authenticated=False, verification_passed=True)
    )


def test_can_claim_only_when_fully_proven() -> None:
    assert can_claim_real_execution(
        ExecutionTruthContext(external_action_performed=True, authenticated=True, verification_passed=True)
    )


def test_execution_claim_error_usable_for_strict_paths() -> None:
    with pytest.raises(ExecutionClaimError):
        raise ExecutionClaimError("Cannot claim execution without real action")
