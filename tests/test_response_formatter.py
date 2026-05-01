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


def test_markdown_link_preserved() -> None:
    s = "Read [this](https://a.io/) and **1.** is fine in prose."
    out = clean_response_formatting(s)
    assert "https://a.io/" in out
    assert "[this]" in out


def test_idempotent_double_pass() -> None:
    a = "x\n*#- y\n**1.** z"
    once = clean_response_formatting(a)
    twice = clean_response_formatting(once)
    assert once == twice


def test_numbered_tight_stacked_markers() -> None:
    s = "Line up:\n1.*# First item\n2.*# Product B\n3.  plain"
    out = clean_response_formatting(s)
    assert "1.*#" not in out
    assert "2.*#" not in out
    assert "1. First" in out
    assert "2. Product" in out


def test_dash_then_star_bullet() -> None:
    s = "Notes\n- * Item A\n- * Item B"
    out = clean_response_formatting(s)
    assert "- * " not in out
    assert "Item A" in out and "Item B" in out


def test_bold_dash_lead() -> None:
    s = "Try:\n**- first step\n**- next"
    out = clean_response_formatting(s)
    assert "**- " not in out
    assert "first step" in out


def test_paragraph_spacers_preserved() -> None:
    s = "Intro here.\n\n- one\n- two\n\n## Next\n\nok"
    out = clean_response_formatting(s)
    assert "\n\n" in out
    assert "## Next" in out


def test_combined_mess_idempotent() -> None:
    a = "List:\n* Item\n- * Odd\n*#- x\n1.*# y\n**- z\n**1.** n"
    once = clean_response_formatting(a)
    assert clean_response_formatting(once) == once
