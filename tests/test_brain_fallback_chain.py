# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.brain.brain_selection import select_brain_for_task


def test_fallback_chain_present() -> None:
    s = select_brain_for_task("repair_plan")
    chain = s.get("fallback_chain")
    assert isinstance(chain, list)
    assert chain
