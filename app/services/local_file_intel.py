"""
In-memory analysis of bundled file reads — no indexing, no persistence.

Uses the LLM only for summarization / reasoning over text already returned by the host executor.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.core.config import get_settings
from app.services.safe_llm_gateway import sanitize_text

logger = logging.getLogger(__name__)

FILE_MARK_RE = re.compile(r"^=== FILE:\s*(.+?)\s*===\s*$", re.MULTILINE)

_INTEL_SYSTEM = """You are Nexa's local file assistant. The user approved a one-time read of files on their machine.
Nothing here is stored or indexed — answer from the excerpts only.

Always respond with exactly these sections (use ### headings):

### Summary

### Key findings

### Relevant files

### Recommendation

If comparison was requested, contrast the files clearly under Key findings.
Be concise. Do not invent file content not shown in the excerpts.
If excerpts were truncated, say so briefly in Summary.
"""


def parse_file_bundle(raw: str) -> list[tuple[str, str]]:
    """Split host_executor ``read_multiple_files`` output into (relative_path, body) pairs."""
    text = raw or ""
    if "=== FILE:" not in text:
        return [("(bundle)", text)] if text.strip() else []

    parts: list[tuple[str, str]] = []
    matches = list(FILE_MARK_RE.finditer(text))
    for i, m in enumerate(matches):
        path = (m.group(1) or "").strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        parts.append((path, body))
    return parts


def chunk_text(text: str, max_chars: int = 3500) -> list[str]:
    """Roughly 500–1000 token windows at ~4 chars/token (in-memory only)."""
    if not text:
        return []
    t = text
    if len(t) <= max_chars:
        return [t]
    return [t[i : i + max_chars] for i in range(0, len(t), max_chars)]


def _fallback_structured_stub(raw_bundle: str, *, operation: str) -> str:
    preview = (raw_bundle or "").strip()
    if len(preview) > 6000:
        preview = preview[:5900] + "\n… [truncated for display]"
    return (
        "### Summary\n\n"
        "Host executor returned file contents (read-only). "
        "No LLM is configured (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`), so this is a raw excerpt.\n\n"
        "### Key findings\n\n"
        f"- Operation: **{operation}**\n"
        "- Configure an API key in `.env` for AI summaries.\n\n"
        "### Relevant files\n\n"
        "(See excerpt headers below.)\n\n"
        "### Recommendation\n\n"
        "Add a model key and re-run the job to get a synthesized analysis.\n\n"
        "---\n\n"
        f"{preview}"
    )


def analyze_local_file_bundle(
    *,
    user_question: str,
    operation: str,
    raw_bundle: str,
) -> str:
    """
    Produce structured markdown from read_multiple_files output.

    Does not persist data. Sanitizes text before any external LLM call.
    """
    s = get_settings()
    max_prompt = min(
        max(int(getattr(s, "host_executor_intel_max_prompt_chars", 48_000)), 8_000),
        120_000,
    )
    bundle = sanitize_text(raw_bundle or "")
    if len(bundle) > max_prompt:
        bundle = bundle[: max_prompt - 200] + "\n\n[… Bundle truncated for analysis …]\n"

    op = (operation or "summarize").strip().lower()
    header = f"Task: {op}\nUser question:\n{sanitize_text((user_question or '').strip()[:4000])}\n\n---\nFile excerpts:\n\n"

    prompt = _INTEL_SYSTEM + "\n\n" + header + bundle

    try:
        from app.services.llm_service import call_primary_llm_text

        out = call_primary_llm_text(prompt)
        return (out or "").strip() or _fallback_structured_stub(raw_bundle, operation=op)
    except Exception as e:
        logger.warning("local_file_intel LLM failed: %s", e)
        return _fallback_structured_stub(raw_bundle, operation=op)


def maybe_finalize_intel_result(payload: dict[str, Any], raw_executor_output: str) -> str:
    """If payload requests intel analysis, run LLM layer; else pass through."""
    pl = dict(payload or {})
    if not pl.get("intel_analysis"):
        return raw_executor_output
    if (pl.get("host_action") or "").strip().lower() != "read_multiple_files":
        return raw_executor_output
    q = str(pl.get("intel_question") or pl.get("user_instruction") or "Summarize these files.")
    op = str(pl.get("intel_operation") or "summarize")
    return analyze_local_file_bundle(user_question=q, operation=op, raw_bundle=raw_executor_output)
