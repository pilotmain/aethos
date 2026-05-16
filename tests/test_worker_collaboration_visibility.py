# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.worker_collaboration_visibility import build_worker_collaboration_chains


def test_collaboration_chain_shape() -> None:
    chains = build_worker_collaboration_chains(limit=4)
    assert isinstance(chains, list)
