# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_worker_followup_resolution import test_what_did_you_find_uses_session_worker


def test_e2e_research_followup() -> None:
    test_what_did_you_find_uses_session_worker()
