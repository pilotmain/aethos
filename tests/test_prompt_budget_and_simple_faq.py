# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Prompt tiers + canned Nexa product FAQs."""

from __future__ import annotations

from app.services.owner_identity_faq import try_canned_nexa_product_faq
from app.services.prompt_budget import classify_prompt_budget_tier


def test_who_created_nexa_is_canned_no_llm_needed() -> None:
    out = try_canned_nexa_product_faq("Who created Nexa?")
    assert out and "Raya" in out


def test_list_files_is_tier2_full_composer() -> None:
    assert (
        classify_prompt_budget_tier("list files in /Users/x/y", intent="general") == 2
    )


def test_short_what_question_is_tier0_or_tier1() -> None:
    assert classify_prompt_budget_tier("What is the capital of France?", intent="general") in (
        0,
        1,
    )
