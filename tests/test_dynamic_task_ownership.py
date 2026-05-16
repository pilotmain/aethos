# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_ownership import build_ownership_chains


def test_ownership_list() -> None:
    chains = build_ownership_chains()
    assert isinstance(chains, list)
