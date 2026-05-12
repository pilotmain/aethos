# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Tests for user-facing list/bullet response cleanup."""
from app.services.response_formatter import clean_response_formatting


def test_unbolds_numbered_list_markers() -> None:
    s = "Here is the list:\n**1.** First\n**2.** Second"
    out = clean_response_formatting(s)
    assert "**1.**" not in out
    assert "1. First" in out
    assert "2. Second" in out
    assert "1.  First" not in out


def test_number_line_leading_junk() -> None:
    s = "Intro\n*#- Item one\n  2.* # mixed"
    out = clean_response_formatting(s)
    assert "*#-" not in out
    assert "Item one" in out
    assert "2. mixed" in out


def test_symbol_stack_bullet() -> None:
    s = "See:\n*#- First point\n- normal"
    out = clean_response_formatting(s)
    assert "*#-" not in out
    assert out.count("- First") >= 1


def test_headings_preserved() -> None:
    s = "## Section\n\n- a\n- b"
    out = clean_response_formatting(s)
    assert "## Section" in out


def test_fenced_code_untouched() -> None:
    s = "Before\n\n```\n* 1. **not** real\n*#- noise\n```\n\nAfter"
    out = clean_response_formatting(s)
    assert "*#- noise" in out
    assert "After" in out
