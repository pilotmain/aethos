# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Detect 'create a project plan PDF for …' style requests; build templated markdown bodies."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services import document_templates as dt

# Short topic lines after "for …" are still valid (e.g. "for my Nexa web UI work").
_MIN_MEANINGFUL = 12


@dataclass
class TemplateDocumentRequest:
    format: str
    template: str
    source_type: str
    label: str


def _format_from_text(low: str) -> str:
    if re.search(r"\b(docx|ms word|word)\b", low):
        return "docx"
    if re.search(r"\b(pdf)\b", low):
        return "pdf"
    if re.search(r"\b(markdown|\.md)\b", low) or " as md" in low:
        return "md"
    if re.search(r"\b(plain text|\.txt|as text)\b", low):
        return "txt"
    if "word" in low and "password" not in low:
        return "docx"
    return "pdf"


def _template_from_text(low: str) -> str | None:
    if "meeting" in low and "note" in low:
        return "meeting_notes"
    if "research brief" in low or ("research" in low and "brief" in low):
        return "research_brief"
    if "project plan" in low or ("project" in low and "plan" in low):
        return "project_plan"
    if "proposal" in low:
        return "proposal"
    if re.search(r"\b(report)\b", low) and "support" not in low:
        return "report"
    return None


def is_template_document_intent(text: str) -> bool:
    t = (text or "").strip()
    if not t or t.startswith("/"):
        return False
    low = t.lower()
    if not any(
        w in low
        for w in (
            "create a",
            "create an",
            "create ",
            "make a",
            "make me a",
            "generate a",
            "turn this into a",
            "turn into a",
        )
    ):
        return False
    if not any(x in low for x in ("pdf", "docx", "word", "markdown", "md", "txt", "document", "file")):
        return False
    if _template_from_text(low) is None:
        return False
    return True


def _focus_snippet(t: str) -> str:
    m = re.search(
        r"(?i)\bfor\s+([^\n.!?]+(?:\s+[^\n.!?]+)*)",
        t,
    )
    if m:
        return m.group(1).strip()[:2000]
    m2 = re.search(
        r"(?i)\babout\s+([^\n.!?]+(?:\s+[^\n.!?]+)*)",
        t,
    )
    if m2:
        return m2.group(1).strip()[:2000]
    m3 = re.search(r"(?i)\bmy\s+([a-z0-9][a-z0-9\s,/-]{3,200})", t)
    if m3:
        return f"My {m3.group(1).strip()}"[:2000]
    return ""


def _uses_last_response(low: str) -> bool:
    if "last" in low and any(x in low for x in ("message", "reply", "response", "answer")):
        return True
    if re.search(
        r"\b(this|that)\s+(summary|message|response|reply|text)\b",
        low,
    ):
        return True
    if "this summary" in low or "from this" in low:
        return True
    return False


def build_templated_markdown(
    template: str,
    body_focus: str,
    *,
    title_guess: str = "",
) -> str:
    title = (title_guess or body_focus or "Nexa document")[:200]
    b = (body_focus or "—").strip()
    if template == "project_plan":
        return dt.format_project_plan(b, title=title)
    if template == "proposal":
        return dt.format_proposal(b, title=title)
    if template == "research_brief":
        return dt.format_research_brief(b, title=title)
    if template == "meeting_notes":
        return dt.format_meeting_notes(b, title=title)
    if template == "report":
        return dt.format_report_markdown(b, title=title)
    return dt.format_report_markdown(b, title=title)


def parse_template_document_request(
    user_text: str,
    last_assistant_text: str | None,
) -> tuple[TemplateDocumentRequest | None, str | None, str | None]:
    """
    Returns (request, body_markdown, clarify_message).
    If clarify_message is set, do not generate — ask the user.
    """
    t = (user_text or "").strip()
    if not is_template_document_intent(t):
        return None, None, None
    low = t.lower()
    template = _template_from_text(low)
    if not template:
        return None, None, None
    fmt = _format_from_text(low)
    st_map = {
        "project_plan": "project_plan",
        "proposal": "proposal",
        "research_brief": "research_brief",
        "meeting_notes": "meeting_notes",
        "report": "report",
    }
    source_type = st_map.get(template, "report")
    labels = {
        "project_plan": "Project plan",
        "proposal": "Proposal",
        "research_brief": "Research brief",
        "meeting_notes": "Meeting notes",
        "report": "Report",
    }
    label = labels.get(template, "Document")
    use_last = _uses_last_response(low)
    focus = _focus_snippet(t)
    body_src = ""
    if use_last and (last_assistant_text or "").strip():
        body_src = (last_assistant_text or "").strip()
    elif focus:
        body_src = focus
    else:
        body_src = t

    if len((body_src or "").strip()) < _MIN_MEANINGFUL and not (use_last and (last_assistant_text or "").strip()):
        return (
            None,
            None,
            "What content should I include in the document? Describe the topic, or say “use your last message” after I have replied, then ask again.",
        )
    if use_last and not (last_assistant_text or "").strip():
        return (
            None,
            None,
            "What content should I include? I do not have a previous assistant message in this thread yet. Ask a question, then request the document, or describe what to put in the file now.",
        )

    title_g = focus[:120] if focus else label
    body_md = build_templated_markdown(
        template,
        body_src,
        title_guess=title_g,
    )
    return (
        TemplateDocumentRequest(
            format=fmt,
            template=template,
            source_type=source_type,
            label=label,
        ),
        body_md,
        None,
    )
