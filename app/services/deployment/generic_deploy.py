# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Execute deploy steps from ``clouds.yaml`` provider entries (argv-only; no shell)."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

from app.services.deployment.project_layout import bundle_deploy_metadata

_SECRET_REF = re.compile(r"\{\{\s*secrets\.(\w+)\s*\}\}")


def render_template(template: str, context: dict[str, Any]) -> str:
    """Replace ``{variable}`` placeholders (simple string replace)."""
    out = str(template or "")
    for key, value in (context or {}).items():
        out = out.replace("{" + str(key) + "}", str(value))
    return out


def _resolve_env_value(raw: str) -> str:
    s = str(raw or "")

    def _sub(m: re.Match[str]) -> str:
        env_key = (m.group(1) or "").strip()
        return os.environ.get(env_key, "")

    return _SECRET_REF.sub(_sub, s)


def _merged_env(spec_env: dict[str, Any] | None) -> dict[str, str]:
    base = {k: str(v) for k, v in os.environ.items() if isinstance(k, str)}
    if not spec_env or not isinstance(spec_env, dict):
        return base
    for k, v in spec_env.items():
        if not isinstance(k, str):
            continue
        if isinstance(v, (str, int, float)):
            base[k] = _resolve_env_value(str(v))
    return base


def _run_argv(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        shell=False,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _argv_from_cmd(cmd: str, context: dict[str, Any]) -> list[str] | None:
    rendered = render_template(cmd, context).strip()
    if not rendered:
        return None
    try:
        return shlex.split(rendered, posix=os.name != "nt")
    except ValueError:
        return None


def _shell_meta(cmd: str) -> bool:
    return any(tok in cmd for tok in (";", "|", "`", "$(", "${", "\n", "\r", "&&", "||"))


def deploy_argv0_on_path(deploy_cmd: str, *, project_name: str) -> bool:
    """True if ``deploy_cmd`` (rendered with dummy context for ``requires``) starts with a binary on PATH."""
    import shutil

    ctx = {"project": project_name, "bucket": "placeholder-bucket", "site": "placeholder-site"}
    rendered = render_template(str(deploy_cmd or ""), ctx).strip()
    if not rendered or _shell_meta(rendered):
        return False
    try:
        argv = shlex.split(rendered, posix=os.name != "nt")
    except ValueError:
        return False
    return bool(argv) and shutil.which(argv[0]) is not None


def deploy_from_yaml_spec(
    *,
    provider_slug: str,
    spec: dict[str, Any],
    project_path: str,
    preview: bool,
    timeout_seconds: float,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run ``pre_deploy``, optional ``login_probe``, then ``deploy_cmd`` / ``deploy_cmd_preview``.

    Commands are parsed with :func:`shlex.split` (no shell). ``deploy_cmd`` must not contain
    shell metacharacters (``;``, pipes, ``&&``, …).
    """
    root = Path(project_path).expanduser().resolve()
    if not root.is_dir():
        return {
            "success": False,
            "error": f"Not a directory: {root}",
            "provider": provider_slug,
            "preview": preview,
        }

    ctx: dict[str, Any] = {"project": root.name, **(context or {})}

    requires = spec.get("requires") or []
    if isinstance(requires, list):
        missing = [str(r) for r in requires if str(r).strip() and str(r).strip() not in ctx]
        if missing:
            return {
                "success": False,
                "error": f"Missing required context for {provider_slug}: {missing}",
                "provider": provider_slug,
                "preview": preview,
            }

    deploy_key = "deploy_cmd_preview" if preview else "deploy_cmd"
    deploy_raw = str(spec.get(deploy_key) or spec.get("deploy_cmd") or "").strip()
    if not deploy_raw:
        return {
            "success": False,
            "error": f"No {deploy_key} or deploy_cmd in clouds.yaml for {provider_slug}",
            "provider": provider_slug,
            "preview": preview,
        }
    if _shell_meta(deploy_raw):
        return {
            "success": False,
            "error": "deploy_cmd must be a single argv-safe line (no shell metacharacters)",
            "provider": provider_slug,
            "preview": preview,
        }

    env = _merged_env(spec.get("env") if isinstance(spec.get("env"), dict) else None)

    login_probe = str(spec.get("login_probe") or "").strip()
    if login_probe and not _shell_meta(login_probe):
        argv_probe = _argv_from_cmd(login_probe, ctx)
        if argv_probe:
            try:
                pr = _run_argv(argv_probe, cwd=root, env=env, timeout=min(60.0, timeout_seconds))
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "error": "Login probe timed out",
                    "provider": provider_slug,
                    "login_hint": str(spec.get("login_cmd") or "").strip() or None,
                    "preview": preview,
                }
            except Exception as exc:  # noqa: BLE001
                return {
                    "success": False,
                    "error": str(exc),
                    "provider": provider_slug,
                    "preview": preview,
                }
            if pr.returncode != 0:
                hint = str(spec.get("login_cmd") or "").strip()
                tail = (pr.stderr or pr.stdout or "").strip()[:800]
                return {
                    "success": False,
                    "error": f"Not logged in or probe failed for {provider_slug}: {tail}" if tail else "Login probe failed",
                    "provider": provider_slug,
                    "requires_login": True,
                    "login_command": hint or None,
                    "login_hint": hint or None,
                    "preview": preview,
                }

    pre = str(spec.get("pre_deploy") or "").strip()
    if pre and not _shell_meta(pre):
        argv_pre = _argv_from_cmd(pre, ctx)
        if argv_pre:
            try:
                pre_r = _run_argv(argv_pre, cwd=root, env=env, timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "error": "pre_deploy timed out",
                    "provider": provider_slug,
                    "preview": preview,
                }
            except Exception as exc:  # noqa: BLE001
                return {
                    "success": False,
                    "error": str(exc),
                    "provider": provider_slug,
                    "preview": preview,
                }
            if pre_r.returncode != 0:
                err = (pre_r.stderr or pre_r.stdout or "").strip()[:4000]
                return {
                    "success": False,
                    "error": f"pre_deploy failed: {err or pre_r.returncode}",
                    "provider": provider_slug,
                    "preview": preview,
                }

    argv_deploy = _argv_from_cmd(deploy_raw, ctx)
    if not argv_deploy:
        return {
            "success": False,
            "error": "Could not parse deploy_cmd",
            "provider": provider_slug,
            "preview": preview,
        }
    try:
        proc = _run_argv(argv_deploy, cwd=root, env=env, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Deployment timed out after {int(timeout_seconds)} seconds",
            "provider": provider_slug,
            "preview": preview,
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc), "provider": provider_slug, "preview": preview}

    out_blob = (proc.stdout or "") + (proc.stderr or "")
    url_pattern = spec.get("url_pattern")
    url: str | None = None
    if isinstance(url_pattern, str) and url_pattern.strip():
        pat = url_pattern.strip()
        if "{" in pat:
            candidate = render_template(pat, ctx)
            if candidate.startswith("http"):
                url = candidate
        if url is None and pat:
            m = re.search(pat, out_blob)
            if m:
                url = m.group(0).rstrip(").,]}\"'")

    if not url:
        for m in re.finditer(r"https?://[^\s\"'<>]+", out_blob):
            u = m.group(0).rstrip(").,]}\"'")
            low = u.lower()
            if "localhost" not in low and "127.0.0.1" not in low:
                url = u
                break

    ok = proc.returncode == 0
    cmd_display = " ".join(str(x) for x in argv_deploy)
    err_tail = (proc.stderr or "").strip()[:8000]
    out_tail = (proc.stdout or "").strip()[:12000]

    result: dict[str, Any] = {
        "success": ok,
        "provider": provider_slug,
        "command": cmd_display,
        "stdout": out_tail,
        "stderr": err_tail,
        "url": url,
        "login_hint": str(spec.get("login_cmd") or "").strip() or None,
        "preview": preview,
        "source": "clouds_yaml",
    }
    if ok:
        result.update(bundle_deploy_metadata(root))
    if not ok:
        result["error"] = err_tail or out_tail or f"exit code {proc.returncode}"
    return result


__all__ = [
    "deploy_argv0_on_path",
    "deploy_from_yaml_spec",
    "render_template",
]
