# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Privacy-safe repair evidence collection (Phase 2 Step 7)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from app.privacy.llm_privacy_gate import evaluate_text_egress
from app.privacy.pii_redaction import redact_text
from app.privacy.privacy_policy import current_privacy_mode
from app.providers.provider_privacy import redact_cli_output


def _preview_file(path: Path, *, max_chars: int = 1200) -> str | None:
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return redact_cli_output(raw[:max_chars], max_out=max_chars)


def _list_workspace_files(repo: Path, *, limit: int = 40) -> list[str]:
    names: list[str] = []
    for pattern in ("package.json", "pyproject.toml", "tsconfig.json", "next.config.*", "vercel.json"):
        for p in sorted(repo.glob(pattern))[:8]:
            try:
                names.append(str(p.relative_to(repo)))
            except ValueError:
                names.append(p.name)
    for sub in ("src", "app", "pages"):
        d = repo / sub
        if d.is_dir():
            for p in sorted(d.rglob("*"))[:limit]:
                if p.is_file() and p.suffix in (".ts", ".tsx", ".js", ".jsx", ".py", ".json"):
                    try:
                        names.append(str(p.relative_to(repo)))
                    except ValueError:
                        pass
                if len(names) >= limit:
                    break
        if len(names) >= limit:
            break
    return names[:limit]


def _git_status_preview(repo: Path) -> str | None:
    if not (repo / ".git").is_dir():
        return None
    try:
        proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=20.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = (proc.stdout or "") + (proc.stderr or "")
    return redact_cli_output(out, max_out=2000) if out.strip() else None


def collect_repair_evidence(
    *,
    project_id: str,
    deploy_ctx: dict[str, Any],
    repair_context: dict[str, Any],
    logs_summary: str = "",
) -> dict[str, Any]:
    repo = Path(str(deploy_ctx.get("repo_path") or "")).resolve()
    diagnosis = repair_context.get("diagnosis") if isinstance(repair_context.get("diagnosis"), dict) else {}
    category = str(diagnosis.get("failure_category") or repair_context.get("failure_category") or "unknown")

    package_scripts: dict[str, str] = {}
    pkg = repo / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            scripts = data.get("scripts") if isinstance(data, dict) else {}
            if isinstance(scripts, dict):
                package_scripts = {str(k): str(v) for k, v in scripts.items() if k and v}
        except (OSError, json.JSONDecodeError):
            pass

    logs_redacted = redact_cli_output(logs_summary or "", max_out=4000)
    from app.core.config import get_settings

    s = get_settings()
    egress = evaluate_text_egress(logs_redacted, boundary="repair_evidence", settings=s)
    mode = current_privacy_mode(s)
    redacted = False
    if mode.value == "redact" and egress.get("pii_categories"):
        logs_redacted = redact_text(logs_redacted)
        redacted = True

    evidence: dict[str, Any] = {
        "project_id": project_id,
        "repo_path": str(repo),
        "failure_category": category,
        "provider": deploy_ctx.get("provider") or "vercel",
        "logs_summary": logs_redacted,
        "workspace_files": _list_workspace_files(repo),
        "package_scripts": package_scripts,
        "verification_output": repair_context.get("verification") or {},
        "package_json_preview": _preview_file(pkg),
        "pyproject_preview": _preview_file(repo / "pyproject.toml"),
        "git_status_preview": _git_status_preview(repo),
        "deployment_diagnostics": {
            "workspace_confidence": deploy_ctx.get("workspace_confidence"),
            "confidence_signals": deploy_ctx.get("confidence_signals") or [],
        },
        "privacy": {
            "scanned": True,
            "redacted": redacted,
            "findings": list(egress.get("pii_categories") or []),
            "egress_allowed": bool(egress.get("allowed", True)),
        },
    }
    return evidence
