"""Enhanced synchronous security review for ``@qa_agent`` / QA domain sub-agents."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.services.qa_agent.advanced_scanner import AdvancedSecurityScanner
from app.services.qa_agent.security_config import SecurityScannerConfig
from app.services.sub_agent_registry import SubAgent
from app.services.workspace_resolver import extract_path_hint_from_message, resolve_workspace_path

_MAX_FILES = 8000
_MAX_FILE_BYTES = 2_000_000
_MAX_LOW_UNSAFE = 25
_TEXT_SUFFIXES = frozenset(
    {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml", ".env", ".toml", ".md", ".sh", ".go", ".rs"}
)

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"-----BEGIN RSA PRIVATE KEY-----"), "Private RSA key", "HIGH"),
    (re.compile(r"-----BEGIN EC PRIVATE KEY-----"), "Private EC key", "HIGH"),
    (re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----"), "SSH private key", "HIGH"),
    (re.compile(r"-----BEGIN (RSA |OPENSSH )?PRIVATE KEY-----"), "Private key material", "HIGH"),
    (re.compile(r"\bsk-[a-zA-Z0-9]{48}\b"), "OpenAI API key shape", "HIGH"),
    (re.compile(r"\bghp_[a-zA-Z0-9]{36}\b"), "GitHub PAT shape", "HIGH"),
    (re.compile(r"\bgho_[a-zA-Z0-9]{36}\b"), "GitHub OAuth token shape", "HIGH"),
    (
        re.compile(r"xox[baprs]-[0-9]{12}-[0-9]{12}-[0-9a-zA-Z]{24}"),
        "Slack token shape",
        "HIGH",
    ),
    (
        re.compile(r"(api[_-]?key|apikey)\s*=\s*['\"]([^'\"]{8,})['\"]", re.I),
        "Possible hardcoded API key assignment",
        "MEDIUM",
    ),
    (
        re.compile(r"password\s*=\s*['\"]([^'\"]{8,})['\"]", re.I),
        "Possible hardcoded password",
        "MEDIUM",
    ),
    (
        re.compile(r"token\s*=\s*['\"]([^'\"]{8,})['\"]", re.I),
        "Possible hardcoded token",
        "MEDIUM",
    ),
    (
        re.compile(r"secret\s*=\s*['\"]([^'\"]{8,})['\"]", re.I),
        "Possible hardcoded secret",
        "MEDIUM",
    ),
    (re.compile(r"AWS[A-Z0-9]{16,}"), "AWS access key id shape", "MEDIUM"),
    (re.compile(r"\bsk-[a-zA-Z0-9]{40,}\b"), "API key-shaped token (sk-…)", "MEDIUM"),
]

_UNSAFE_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\beval\s*\("), "Use of eval()", "HIGH"),
    (re.compile(r"\bexec\s*\("), "Use of exec()", "HIGH"),
    (re.compile(r"subprocess\.call\([^)]*shell\s*=\s*True"), "subprocess shell=True", "HIGH"),
    (re.compile(r"subprocess\.(?:run|Popen)\([^)]*shell\s*=\s*True"), "subprocess shell=True", "HIGH"),
    (re.compile(r"\bos\.system\s*\("), "os.system()", "HIGH"),
    (re.compile(r"\b__import__\s*\("), "Dynamic __import__()", "MEDIUM"),
    (re.compile(r"\bconsole\.log\s*\("), "console.log (review for prod)", "LOW"),
    (re.compile(r"\bprint\s*\("), "print() (review for prod)", "LOW"),
]


def _heuristic_scan(root: Path, extra_ignores: list[str]) -> dict[str, list[dict[str, Any]]]:
    secrets: list[dict[str, Any]] = []
    unsafe: list[dict[str, Any]] = []
    n_files = 0
    low_unsafe = 0

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [d for d in dirnames if d not in SecurityScannerConfig.IGNORE_DIRS]
        for name in filenames:
            if n_files >= _MAX_FILES:
                return {"secrets": secrets, "unsafe": unsafe}
            fp = Path(dirpath) / name
            sp = str(fp)
            if SecurityScannerConfig.should_ignore_file(sp, root, extra_patterns=extra_ignores):
                continue
            suf = Path(name).suffix.lower()
            if name != ".env" and suf not in _TEXT_SUFFIXES:
                continue
            try:
                if fp.stat().st_size > _MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            n_files += 1
            try:
                text = fp.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            is_test = SecurityScannerConfig.is_likely_test_file(sp)

            for line_num, line in enumerate(text.splitlines(), 1):
                for pat, desc, severity in _SECRET_PATTERNS:
                    if pat.search(line):
                        final_sev = severity
                        if is_test and severity == "HIGH":
                            final_sev = "LOW"
                        elif is_test and severity == "MEDIUM":
                            final_sev = "LOW"
                        secrets.append(
                            {
                                "file": sp,
                                "line": line_num,
                                "description": desc,
                                "severity": final_sev,
                                "is_test": is_test,
                                "source": "heuristic",
                            }
                        )
                        break

                for pat, desc, severity in _UNSAFE_PATTERNS:
                    if pat.search(line):
                        if severity == "LOW":
                            low_unsafe += 1
                            if low_unsafe > _MAX_LOW_UNSAFE:
                                continue
                        unsafe.append(
                            {
                                "file": sp,
                                "line": line_num,
                                "description": desc,
                                "severity": severity,
                                "source": "heuristic",
                            }
                        )
                        break

    return {"secrets": secrets, "unsafe": unsafe}


def _dependency_hints(root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    req = root / "requirements.txt"
    if req.is_file():
        out.append(
            {
                "issue": "Run pip-audit against requirements.txt for CVE coverage",
                "severity": "INFO",
                "file": str(req),
            }
        )
    pkg = root / "package.json"
    if pkg.is_file():
        out.append(
            {
                "issue": "Run npm audit / pnpm audit for dependency vulnerabilities",
                "severity": "INFO",
                "file": str(pkg),
            }
        )
    return out


def _flatten_finding(obj: Any, default_severity: str = "HIGH") -> dict[str, Any]:
    if not isinstance(obj, dict):
        return {"description": str(obj)[:200], "file": "", "line": 0, "severity": default_severity}
    desc = (
        obj.get("Description")
        or obj.get("description")
        or obj.get("DetectorName")
        or obj.get("RuleID")
        or "Finding"
    )
    path = obj.get("File") or obj.get("file") or obj.get("path") or obj.get("Path") or ""
    line = obj.get("StartLine") or obj.get("line") or obj.get("Line") or 0
    try:
        line = int(line)
    except (TypeError, ValueError):
        line = 0
    return {"description": str(desc), "file": str(path), "line": line, "severity": default_severity}


def format_security_report(results: dict[str, Any]) -> str:
    """Format merged scan results (also used by tests / callers)."""
    merged = dict(results)
    if "unsafe" not in merged and merged.get("unsafe_patterns"):
        merged["unsafe"] = merged["unsafe_patterns"]
    if "dependency_hints" not in merged and merged.get("dependencies"):
        merged["dependency_hints"] = merged["dependencies"]
    merged.setdefault("gitleaks", {})
    merged.setdefault("trufflehog", {})
    merged.setdefault("pip_audit", {})
    merged.setdefault("scanner_meta", {})
    return _format_enhanced_report(merged)


def _format_enhanced_report(results: dict[str, Any]) -> str:
    root = results.get("root") or ""
    secrets: list[dict[str, Any]] = list(results.get("secrets") or [])
    unsafe: list[dict[str, Any]] = list(results.get("unsafe") or [])
    gl = results.get("gitleaks") or {}
    th = results.get("trufflehog") or {}
    pip = results.get("pip_audit") or {}
    meta = results.get("scanner_meta") or {}

    real_secrets = [
        s for s in secrets if (not s.get("is_test")) and s.get("severity") in ("HIGH", "MEDIUM")
    ]
    test_secrets = [
        s for s in secrets if s.get("is_test") or s.get("severity") == "LOW"
    ]

    high_u = [u for u in unsafe if u.get("severity") == "HIGH"]
    med_u = [u for u in unsafe if u.get("severity") == "MEDIUM"]
    low_u = [u for u in unsafe if u.get("severity") == "LOW"]

    gl_findings = gl.get("findings") or []
    th_findings = th.get("findings") or []
    pip_v = pip.get("vulnerabilities") or []

    lines: list[str] = [
        "🔒 **Security scan (enhanced)**",
        "",
        f"**Root:** `{root}`",
        "",
        "### 📊 Summary",
        f"- Heuristic non-test signals: **{len(real_secrets)}**",
        f"- Heuristic test/fixture downgraded rows: **{len(test_secrets)}**",
        f"- Unsafe (HIGH/MEDIUM/LOW): **{len(high_u)}** / **{len(med_u)}** / **{len(low_u)}**",
        f"- Gitleaks findings: **{len(gl_findings)}** ({'yes' if gl.get('available') else 'n/a'})",
        f"- Trufflehog findings: **{len(th_findings)}** ({'yes' if th.get('available') else 'n/a'})",
        f"- pip-audit CVE rows: **{len(pip_v)}** ({'yes' if pip.get('available') else 'n/a'})",
        "",
    ]

    if real_secrets:
        lines.append("### 🔴 Heuristic — review first (non-test)")
        for it in real_secrets[:12]:
            lines.append(
                f"- `{it['file']}` L{it['line']}: {it['description']} (**{it.get('severity', '?')}**)"
            )
        if len(real_secrets) > 12:
            lines.append(f"- … and **{len(real_secrets) - 12}** more")
        lines.append("")

    if gl_findings:
        lines.append("### 🧱 Gitleaks")
        for raw in gl_findings[:10]:
            it = _flatten_finding(raw)
            loc = f"L{it['line']} " if it["line"] else ""
            lines.append(f"- `{it['file']}` {loc}{it['description']}")
        if len(gl_findings) > 10:
            lines.append(f"- … and **{len(gl_findings) - 10}** more")
        if gl.get("error"):
            lines.append(f"- _stderr: {gl['error']}_")
        lines.append("")

    if th_findings:
        lines.append("### 🐷 Trufflehog")
        for raw in th_findings[:10]:
            if isinstance(raw, dict):
                det = raw.get("DetectorName") or raw.get("detector_name") or "secret"
                src = raw.get("SourceMetadata") or {}
                fp = ""
                if isinstance(src, dict):
                    d = src.get("Data") or {}
                    if isinstance(d, dict):
                        fp = d.get("path") or d.get("Path") or ""
                lines.append(f"- `{fp or raw}`: **{det}**")
            else:
                lines.append(f"- {str(raw)[:200]}")
        if len(th_findings) > 10:
            lines.append(f"- … and **{len(th_findings) - 10}** more")
        if th.get("error"):
            lines.append(f"- _note: {th['error']}_")
        lines.append("")

    if high_u:
        lines.append("### 🟠 Unsafe — HIGH")
        for it in high_u[:12]:
            lines.append(f"- `{it['file']}` L{it['line']}: {it['description']}")
        if len(high_u) > 12:
            lines.append(f"- … and **{len(high_u) - 12}** more")
        lines.append("")

    if med_u:
        lines.append("### 🟡 Unsafe — MEDIUM")
        for it in med_u[:12]:
            lines.append(f"- `{it['file']}` L{it['line']}: {it['description']}")
        if len(med_u) > 12:
            lines.append(f"- … and **{len(med_u) - 12}** more")
        lines.append("")

    if test_secrets:
        lines.append(
            f"### 🧪 Test / fixture heuristics (likely false positives) — **{len(test_secrets)}** rows"
        )
        lines.append("_Severity downgraded for paths matching test/fixture patterns._")
        lines.append("")

    if low_u:
        lines.append(f"### ⚪ Unsafe — LOW (capped, **{len(low_u)}** shown max {_MAX_LOW_UNSAFE})")
        for it in low_u[:8]:
            lines.append(f"- `{it['file']}` L{it['line']}: {it['description']}")
        lines.append("")

    if pip_v:
        lines.append("### 📦 pip-audit (CVE-style)")
        for row in pip_v[:15]:
            if isinstance(row, dict):
                name = row.get("name") or row.get("package") or row
                vuln = row.get("vulns") or row.get("id") or ""
                lines.append(f"- {name}: {vuln}")
            else:
                lines.append(f"- {row}")
        if len(pip_v) > 15:
            lines.append(f"- … and **{len(pip_v) - 15}** more")
        lines.append("")
    dep_hints = results.get("dependency_hints") or []
    if dep_hints:
        lines.append("### 📦 Dependency hygiene")
        for it in dep_hints[:8]:
            if isinstance(it, dict):
                lines.append(f"- {it.get('issue', it)} (`{it.get('file', '')}`)")
            else:
                lines.append(f"- {it}")
        lines.append("")

    lines.append("### 💡 Recommendations")
    if not meta.get("has_gitleaks"):
        lines.append("- Install **gitleaks** for deeper secret detection (`brew install gitleaks`).")
    if not meta.get("has_trufflehog"):
        lines.append("- Install **trufflehog** for filesystem entropy scans (`brew install trufflehog`).")
    if not meta.get("has_pip_audit"):
        lines.append("- Install **pip-audit**: `pip install pip-audit` then re-run scan.")
    lines.append("- Add repo-root **`.secretsignore`** (globs) for known false positives — merged automatically.")
    lines.append("- Tune **`SecurityScannerConfig`** in code if your repo layout differs.")
    lines.append("")
    lines.append("_Heuristic + optional tools — verify before rotating production secrets._")

    out = "\n".join(lines)
    if len(out) > 14000:
        return out[:13900] + "\n\n… _(truncated)_"
    return out


def run_security_review_sync(
    agent: SubAgent,
    message: str,
    *,
    db: Session | None,
    user_id: str,
) -> str:
    """Resolve workspace, run enhanced scans, return Markdown report."""
    _ = agent
    hint = extract_path_hint_from_message(message)
    try:
        root_path = resolve_workspace_path(hint, db=db, owner_user_id=user_id or None)
    except ValueError as exc:
        return f"❌ {exc}"
    root = Path(root_path).resolve()
    if not root.is_dir():
        return f"❌ Not a directory: {root_path}"

    extra = SecurityScannerConfig.load_secretsignore(root)
    issues = _heuristic_scan(root, extra)
    scanner = AdvancedSecurityScanner(root)

    gl = scanner.scan_with_gitleaks()
    th = scanner.scan_with_trufflehog()
    pip_res = scanner.scan_dependencies()

    pip_ok = bool(pip_res.get("available"))
    hints = _dependency_hints(root)

    results: dict[str, Any] = {
        "root": str(root),
        "secrets": issues["secrets"],
        "unsafe": issues["unsafe"],
        "dependency_hints": hints,
        "gitleaks": gl,
        "trufflehog": th,
        "pip_audit": pip_res,
        "scanner_meta": {
            "has_gitleaks": scanner.has_gitleaks,
            "has_trufflehog": scanner.has_trufflehog,
            "has_pip_audit": scanner.has_pip_audit or pip_ok,
        },
    }

    return _format_enhanced_report(results)


__all__ = ["format_security_report", "run_security_review_sync"]
