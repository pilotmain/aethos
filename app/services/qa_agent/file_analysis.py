# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Workspace-local static analysis hints for QA agents (sync, no LLM)."""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import get_settings


_PATH_RE = re.compile(r"(/[A-Za-z0-9_./\\-]+\.[A-Za-z0-9]{1,16})\b")


def _allowed_roots() -> list[Path]:
    s = get_settings()
    roots: list[Path] = []
    for raw in (
        getattr(s, "host_executor_work_root", "") or "",
        getattr(s, "nexa_workspace_root", "") or "",
    ):
        t = (raw or "").strip()
        if not t:
            continue
        try:
            roots.append(Path(t).expanduser().resolve())
        except OSError:
            continue
    return roots


def _is_under_allowed(path: Path) -> bool:
    rp = path.resolve()
    for root in _allowed_roots():
        try:
            rp.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def run_qa_file_analysis(message: str, *, max_lines: int = 100) -> str:
    """
    Scan a local file for obvious risk patterns (first ``max_lines`` lines).
    Paths must sit under configured workspace / host executor roots.
    """
    raw = (message or "").strip()
    m = _PATH_RE.search(raw.replace("\\", "/"))
    if not m:
        return (
            "❌ Please include an absolute file path to analyze.\n"
            "Example: `@qa_agent analyze /path/to/app/main.py`"
        )
    file_path = Path(m.group(1))
    try:
        file_path = file_path.expanduser().resolve()
    except OSError as exc:
        return f"❌ Invalid path: {exc}"

    if not _is_under_allowed(file_path):
        return (
            "❌ For safety, analysis is limited to paths under the configured "
            "workspace / host executor roots. Ask for a path inside your project tree."
        )

    if not file_path.is_file():
        return f"❌ File not found: `{file_path}`"

    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"❌ Could not read file: {exc}"

    lines = text.splitlines()
    findings: list[str] = []
    cap = min(max_lines, len(lines))
    for i, line in enumerate(lines[:cap], start=1):
        low = line.lower()
        if "import subprocess" in line:
            findings.append(f"⚠️ Line {i}: `subprocess` import — validate inputs if used.")
        if "eval(" in line:
            findings.append(f"🔴 Line {i}: `eval()` — high risk.")
        if "exec(" in line:
            findings.append(f"🔴 Line {i}: `exec()` — high risk.")
        if "password" in low and "=" in line and not low.strip().startswith("#"):
            findings.append(f"🟡 Line {i}: possible hardcoded credential.")
        if "api_key" in low and "=" in line and not low.strip().startswith("#"):
            findings.append(f"🟡 Line {i}: possible hardcoded API key literal.")

    head = (
        f"🔍 **QA scan**\n\n**File:** `{file_path}`\n"
        f"**Lines scanned:** {cap} / {len(lines)}\n\n"
    )
    if not findings:
        return head + "✅ No obvious high-risk patterns in the scanned span."

    body = "**Findings:**\n" + "\n".join(findings[:20])
    if len(findings) > 20:
        body += f"\n\n… and {len(findings) - 20} more."
    return head + body


__all__ = ["run_qa_file_analysis"]
