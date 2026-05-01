"""Mini-doc style hints and gating; marketing/research section keywords."""
from app.services.structured_response_style import (
    GENERAL_MINI_DOC_SECTIONS,
    MARKETING_MINI_DOC_SECTIONS,
    RESEARCH_MINI_DOC_SECTIONS,
    STRATEGY_MINI_DOC_SECTIONS,
    should_use_structured_style,
    structured_style_guidance_for,
)
from app.services.copilot_next_steps import (
    response_includes_next_steps_block,
    should_append_next_steps,
)
from app.services.response_formatter import clean_response_formatting


def test_marketing_guidance_mentions_key_sections() -> None:
    g = structured_style_guidance_for("marketing", "marketing_web_analysis")
    assert "Insight" in g
    assert "What I found" in g or "what I found" in g.lower()
    assert "Sources" in g
    assert "exactly" in g.lower() and "section" in g.lower()
    # Constants align with spec
    assert "Insight" in MARKETING_MINI_DOC_SECTIONS
    assert "Positioning" in MARKETING_MINI_DOC_SECTIONS


def test_research_guidance_includes_findings_and_sources() -> None:
    g = structured_style_guidance_for("research", "public_web")
    for w in ("Summary", "Findings", "Sources", "Next steps"):
        assert w in g
    assert "Sources" in RESEARCH_MINI_DOC_SECTIONS


def test_hello_does_not_trigger_structured() -> None:
    assert not should_use_structured_style("hello", agent_key="nexa", intent="chat", response_kind=None)
    assert not should_use_structured_style("  hi  ", None, "chat", None)


def test_brief_identity_not_structured() -> None:
    assert not should_use_structured_style(
        "Who is Raya?", agent_key="nexa", intent="chat", response_kind=None
    )


def test_strategy_guidance_sections() -> None:
    g = structured_style_guidance_for("strategy", None)
    for w in ("Situation", "Options", "Recommendation", "Next steps"):
        assert w in g
    for w in STRATEGY_MINI_DOC_SECTIONS:
        assert w in g


def test_general_substantial_guidance_sections() -> None:
    g = structured_style_guidance_for("nexa", None)
    for w in ("Summary", "Key points", "Recommendation", "Next steps"):
        assert w in g
    for label in ("Summary", "Key points", "Recommendation", "Next steps"):
        assert label in GENERAL_MINI_DOC_SECTIONS


def test_marketing_analysis_triggers() -> None:
    assert should_use_structured_style(
        "x",
        agent_key="nexa",
        intent="chat",
        response_kind="marketing_web_analysis",
    )


def test_heading_spacing_normalized_not_code() -> None:
    raw = "Line one\n## Title\n\nHere.\n\n\n\nMore."
    out = clean_response_formatting(raw)
    assert "\n\n\n" not in out
    f = "Before\n```\n## fake\n\n\na\n```\nAfter"
    c = clean_response_formatting(f)
    assert "## fake" in c
    assert c.count("```") == 2 or "```" in c


def test_duplicate_next_steps_append_skipped() -> None:
    body = "Done.\n\n## Next steps\n- one\n"
    assert response_includes_next_steps_block(body)
    assert not should_append_next_steps(
        "clarify",
        "let us plan the launch",
        ["a", "b"],
        assistant_text=body,
    )
    assert should_append_next_steps("clarify", "let us plan the launch", ["a", "b"], assistant_text="Only text.")


def test_next_steps_colon_in_body() -> None:
    assert response_includes_next_steps_block("Intro\n\nNext steps:\n- a")


def test_next_step_singular_heading_skips_append() -> None:
    body = "Summary\n\n## Next step\n- one thing\n"
    assert response_includes_next_steps_block(body)
    assert not should_append_next_steps("clarify", "let us plan", ["a"], assistant_text=body)
