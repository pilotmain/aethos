# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Outbound network egress policy (Phase 54 MVP)."""

from app.services.network_policy.policy import (
    assert_provider_egress_allowed,
    is_egress_allowed,
    record_egress_attempt,
)

__all__ = ["assert_provider_egress_allowed", "is_egress_allowed", "record_egress_attempt"]
