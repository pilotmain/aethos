"""
Static analysis for PR diffs (Python / JS / security heuristics).
"""

from __future__ import annotations

import fnmatch
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)


def parse_ignore_patterns(raw: str) -> list[str]:
    return [p.strip() for p in (raw or "").split(",") if p.strip()]


class PRAnalyzer:
    """Analyze PR file contents for issues and suggestions."""

    def __init__(self, ignore_patterns: list[str] | None = None) -> None:
        self.ignore_patterns = list(ignore_patterns or [])

    def should_ignore_file(self, file_path: str) -> bool:
        base = os.path.basename(file_path)
        for pattern in self.ignore_patterns:
            if not pattern:
                continue
            if "*" in pattern or "?" in pattern or "[" in pattern:
                if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(base, pattern):
                    return True
            elif pattern in file_path or pattern == base:
                return True
        return False

    async def analyze_file(self, file_path: str, patch: str, content: str) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        if file_path.endswith(".py"):
            issues.extend(self._check_python(content, file_path))
        elif file_path.endswith((".js", ".ts", ".jsx", ".tsx")):
            issues.extend(self._check_javascript(content, file_path))
        issues.extend(self._check_security(content, file_path))
        return issues

    def _check_python(self, content: str, file_path: str) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        for i, line in enumerate(content.split("\n"), 1):
            if re.search(r"\bprint\s*\(", line) and "debug" not in line.lower() and "# noqa" not in line:
                issues.append(
                    {
                        "line": i,
                        "message": "Consider using logging instead of print() for production code",
                        "severity": "info",
                        "suggestion": "Replace `print()` with `logger.info()`",
                    }
                )
            if re.search(r"except\s*:", line) and "except Exception" not in line:
                issues.append(
                    {
                        "line": i,
                        "message": "Bare except catches SystemExit and KeyboardInterrupt",
                        "severity": "warning",
                        "suggestion": "Use `except Exception:` or catch specific exceptions",
                    }
                )
            stripped = line.strip()
            if (
                stripped.startswith("def ")
                and stripped.endswith("):")
                and "->" not in line
                and not any(x in stripped for x in ("__init__", "__str__", "__repr__", "test_", "mock_"))
            ):
                issues.append(
                    {
                        "line": i,
                        "message": "Consider adding a return type hint",
                        "severity": "info",
                        "suggestion": f"Add `-> None` or an explicit return type",
                    }
                )
        return issues

    def _check_javascript(self, content: str, file_path: str) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        for i, line in enumerate(content.split("\n"), 1):
            if "console.log" in line or "console.debug" in line:
                if "eslint-disable" in line or "no-console" in line:
                    continue
                issues.append(
                    {
                        "line": i,
                        "message": "Remove console.log before merging",
                        "severity": "warning",
                        "suggestion": "Use a logging framework or remove",
                    }
                )
            if re.search(r"\bvar\s+", line):
                issues.append(
                    {
                        "line": i,
                        "message": "Prefer `let` or `const` instead of `var`",
                        "severity": "info",
                        "suggestion": "Replace `var` with `const` or `let`",
                    }
                )
        return issues

    def _check_security(self, content: str, file_path: str) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        for i, line in enumerate(content.split("\n"), 1):
            low = line.lower()
            if line.strip().startswith("#") or line.strip().startswith("//") or line.strip().startswith("*"):
                continue
            secrets_kw = ("password", "secret", "api_key", "apikey", "token")
            if any(k in low for k in secrets_kw) and "=" in line:
                if re.search(r"os\.environ|getenv|process\.env", line):
                    continue
                if re.search(r"\b(?:false|true|null|\[\])\s*$", line.strip()):
                    continue
                issues.append(
                    {
                        "line": i,
                        "message": "Potential hardcoded secret or credential-like assignment",
                        "severity": "error",
                        "suggestion": "Use environment variables or a secret manager",
                    }
                )
                continue

            if "execute(" in line and "+" in line and ("sql" in low or "query" in low or "cursor" in low):
                issues.append(
                    {
                        "line": i,
                        "message": "Potential SQL injection risk with string concatenation",
                        "severity": "error",
                        "suggestion": "Use parameterized queries",
                    }
                )
            if re.search(r"\beval\s*\(", line):
                issues.append(
                    {
                        "line": i,
                        "message": "`eval()` is dangerous and should be avoided",
                        "severity": "error",
                        "suggestion": "Use a safe parser or structured data",
                    }
                )
        return issues

    async def generate_summary(self, issues: list[dict[str, Any]]) -> str:
        if not issues:
            return "✅ No issues found in this pull request."

        by_severity: dict[str, list[dict[str, Any]]] = {"error": [], "warning": [], "info": []}
        for issue in issues:
            sev = str(issue.get("severity", "info")).lower()
            if sev not in by_severity:
                sev = "info"
            by_severity[sev].append(issue)

        summary = "## PR Review Summary\n\n"
        summary += f"Found **{len(issues)}** findings:\n"
        summary += f"- 🔴 {len(by_severity['error'])} errors\n"
        summary += f"- 🟡 {len(by_severity['warning'])} warnings\n"
        summary += f"- 🔵 {len(by_severity['info'])} suggestions\n\n"

        if by_severity["error"]:
            summary += "### Errors\n"
            for issue in by_severity["error"][:8]:
                loc = issue.get("path", "")
                ln = issue.get("line", "")
                prefix = f"`{loc}:{ln}` — " if loc else ""
                summary += f"- {prefix}{issue.get('message', '')}\n"
            summary += "\n"

        if by_severity["warning"]:
            summary += "### Warnings\n"
            for issue in by_severity["warning"][:8]:
                loc = issue.get("path", "")
                ln = issue.get("line", "")
                prefix = f"`{loc}:{ln}` — " if loc else ""
                summary += f"- {prefix}{issue.get('message', '')}\n"
            summary += "\n"

        if by_severity["info"]:
            summary += "### Suggestions\n"
            for issue in by_severity["info"][:6]:
                loc = issue.get("path", "")
                ln = issue.get("line", "")
                prefix = f"`{loc}:{ln}` — " if loc else ""
                summary += f"- {prefix}{issue.get('message', '')}\n"

        return summary

    async def generate_inline_comments(self, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for issue in issues:
            path = issue.get("path")
            line = issue.get("line")
            if not path or not isinstance(line, int) or line < 1:
                continue
            sev = str(issue.get("severity", "info")).upper()
            body = f"**{sev}**: {issue.get('message', '')}\n\n💡 {issue.get('suggestion', '')}"
            out.append({"path": path, "line": line, "body": body, "side": "RIGHT"})
        return out
