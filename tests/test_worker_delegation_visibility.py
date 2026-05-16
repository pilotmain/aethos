# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_ownership import build_operator_trace_chains


def test_ownership_chains_list() -> None:
    chains = build_operator_trace_chains(None)
    assert isinstance(chains, list)
