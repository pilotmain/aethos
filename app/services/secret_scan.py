"""Heuristic secret detection in diffs and text (best-effort; not a full secrets scanner)."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

# Named patterns for user-facing output
SECRET_PATTERN_DEFS: list[tuple[str, re.Pattern]] = [
    (
        "openai_sk",
        re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    ),
    (
        "anthropic_sk",
        re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    ),
    (
        "pem_key",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ),
    (
        "env_assignment",
        re.compile(r"(?i)(password|api_key|apikey|secret|token)\s*=\s*[^\s\n#]{3,}"),
    ),
]

def scan_text_for_secrets(text: str) -> list[str]:
    findings: list[str] = []
    for name, pat in SECRET_PATTERN_DEFS:
        if pat.search(text or ""):
            findings.append(name)
    return findings


def scan_git_diff_for_secrets(project_root: str | Path) -> list[str]:
    p = Path(project_root)
    result = subprocess.run(
        ["git", "diff", "--unified=0"],
        cwd=str(p),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        return [f"git diff failed: {(result.stderr or result.stdout)[:200]}"]
    return scan_text_for_secrets(result.stdout or "")


def scan_combined_diff_for_secrets(project_root: str | Path, baseline_sha: str) -> list[str]:
    """Diff since baseline (commits) plus unstaged working tree."""
    p = Path(project_root)
    parts: list[str] = []
    r1 = subprocess.run(
        ["git", "diff", f"{baseline_sha}..HEAD"],
        cwd=str(p),
        text=True,
        capture_output=True,
        check=False,
    )
    if r1.returncode in (0, 1) and (r1.stdout or "").strip():
        parts.append(r1.stdout)
    r2 = subprocess.run(
        ["git", "diff"],
        cwd=str(p),
        text=True,
        capture_output=True,
        check=False,
    )
    if r2.returncode in (0, 1) and (r2.stdout or "").strip():
        parts.append(r2.stdout)
    return scan_text_for_secrets("\n".join(parts))
