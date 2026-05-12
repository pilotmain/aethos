# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Pronoun / identity: memory + post-pass + owner FAQ."""
from app.services.memory_preferences import (
    extract_memory_preferences,
    get_effective_owner_pronoun,
    identity_pronoun_system_instructions,
)
from app.services.owner_identity_faq import (
    try_canned_owner_identity_faq,
    is_raya_owner_identity_faq,
)
from app.services.response_formatter import _apply_owner_pronoun_fixes_prose, finalize_user_facing_text


def test_extract_owner_he_from_memory_and_soul() -> None:
    soul = "## Creator\nRaya is male. Pronouns: he/him"
    mem = "Reference: Raya Ameha Meresa is male; use he/him."
    p = extract_memory_preferences(mem, soul)
    assert p.get("owner_third_pronoun") == "he"


def test_effective_pronoun_from_learned_overrides() -> None:
    assert get_effective_owner_pronoun({"learned:owner_pronoun": "they"}) == "they"
    assert get_effective_owner_pronoun({"learned:owner_pronoun": "he"}) == "he"


def test_identity_prompt_mentions_no_name_guess() -> None:
    s = identity_pronoun_system_instructions()
    assert "infer" in s.lower() or "assume" in s.lower()
    assert "name" in s.lower()


def test_raya_canned_uses_he_when_memory_he() -> None:
    # Simulated: effective will read real soul.md in test env; we pass explicit he.
    t = try_canned_owner_identity_faq(
        "Who is Raya?", user_preferences={"learned:owner_pronoun": "he"}
    )
    assert t and "Raya Ameha Meresa" in t
    assert "He is building" in t
    assert " she " not in t.lower()


def test_tell_me_about_raya_canned() -> None:
    t = try_canned_owner_identity_faq(
        "Tell me about Raya", user_preferences={"learned:owner_pronoun": "he"}
    )
    assert t
    assert "he" in t.lower()
    assert " she " not in t.lower()


def test_neutral_when_pronoun_they() -> None:
    t = try_canned_owner_identity_faq(
        "Who is Raya?", user_preferences={"learned:owner_pronoun": "they"}
    )
    assert t and "Raya is building" in t
    assert "He is building" not in t
    assert " she " not in t.lower()


def test_post_pass_fixes_she_on_raya_line() -> None:
    bad = "Raya is the founder. She created Nexa."
    fixed = _apply_owner_pronoun_fixes_prose(bad, "he")
    assert "He created" in fixed
    assert " she " not in fixed.lower()


def test_finalize_does_not_touch_unrelated_she() -> None:
    # No "Raya" in line — no line-level her/she fix
    t = "Jamie said she is done."
    assert finalize_user_facing_text(t, user_preferences={"learned:owner_pronoun": "he"}) == t


def test_faq_matcher() -> None:
    assert is_raya_owner_identity_faq("Who is Raya?")
    assert is_raya_owner_identity_faq("What is Raya")
    assert not is_raya_owner_identity_faq("What is a good GTM for my SaaS product launch?")
