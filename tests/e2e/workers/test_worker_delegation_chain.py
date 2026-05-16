# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_worker_delegation_visibility import test_ownership_chains_list


def test_e2e_delegation_chain() -> None:
    test_ownership_chains_list()
