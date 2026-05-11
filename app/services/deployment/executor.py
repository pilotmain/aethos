"""Run deployment using detected CLIs (subprocess; gateway-safe synchronous API)."""

from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.deployment.detector import DeploymentDetector, _normalize_provider


_LOCALHOST_MARKERS = ("localhost", "127.0.0.1", "0.0.0.0", "example.com")


class DeploymentExecutor:
    """Execute deployment using registry-defined argv or shell commands."""

    @classmethod
    def deploy_sync(
        cls,
        project_path: str,
        *,
        provider: str | None = None,
        preview: bool = False,
        timeout_seconds: float = 300.0,
    ) -> dict[str, Any]:
        """
        Deploy from ``project_path``.

        Candidate order (auto): config files → framework (Next.js→Vercel) → PATH priority list.

        When ``preview`` is True, uses ``deploy_argv_preview`` when defined.
        """
        root = Path(project_path).expanduser().resolve()
        if not root.is_dir():
            return {
                "success": False,
                "error": f"Not a directory: {root}",
                "provider": provider,
                "preview": preview,
            }

        settings = get_settings()
        auto_on = bool(getattr(settings, "nexa_deploy_auto_detect", True))

        if not provider and not auto_on:
            return {
                "success": False,
                "error": (
                    "Auto-detect is disabled (set NEXA_DEPLOY_AUTO_DETECT=true or say "
                    "`deploy to vercel`, `deploy to railway`, …)."
                ),
                "available_detected": [],
                "preview": preview,
            }

        if provider:
            norm = _normalize_provider(provider)
            cfg = DeploymentDetector.get_registry(norm or "")
            if not cfg:
                avail = [c["name"] for c in DeploymentDetector.detect_available(str(root))]
                return {
                    "success": False,
                    "error": f"Unknown provider: {provider}. Installed: {avail or 'none'}",
                    "provider": provider,
                    "available_detected": avail,
                    "preview": preview,
                }
            bin_name = str(cfg.get("binary") or "")
            if not shutil.which(bin_name):
                return {
                    "success": False,
                    "error": f"CLI not on PATH: {bin_name}",
                    "provider": cfg["name"],
                    "login_hint": cfg.get("login_hint"),
                    "preview": preview,
                }
            return cls._run_deploy(cfg, root, timeout_seconds, preview=preview)

        file_hints = DeploymentDetector.detect_by_file(str(root))
        framework = DeploymentDetector.detect_by_framework(str(root))
        available = DeploymentDetector.detect_available(str(root))

        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        for c in file_hints + framework + available:
            name = str(c.get("name") or "")
            if name and name not in seen:
                seen.add(name)
                candidates.append(c)

        if not candidates:
            return {
                "success": False,
                "error": "No deployment CLI found on PATH (install vercel, railway, flyctl, netlify, wrangler, …).",
                "available_detected": [],
                "config_detected": [],
                "preview": preview,
                "suggestion": "Try: npm i -g vercel | brew install railway | https://fly.io/docs/hobbyists/install-flyctl/",
            }

        errors: list[str] = []
        for cfg in candidates:
            name = str(cfg.get("name") or "unknown")
            res = cls._run_deploy(cfg, root, timeout_seconds, preview=preview)
            if res.get("success"):
                res["preview"] = preview
                return res
            err = str(res.get("error") or res.get("stderr") or "failed")
            errors.append(f"{name}: {err[:200]}")

        return {
            "success": False,
            "error": "; ".join(errors) if errors else "All deployment attempts failed.",
            "available_detected": [str(c.get("name")) for c in available],
            "config_detected": [str(c.get("name")) for c in file_hints],
            "framework_detected": [str(c.get("name")) for c in framework],
            "preview": preview,
            "suggestion": (
                "Try: npm i -g vercel · brew install railway · "
                "https://fly.io/docs/hobbyists/install-flyctl/"
            ),
        }

    @classmethod
    async def deploy(
        cls,
        project_path: str,
        *,
        provider: str | None = None,
        preview: bool = False,
        timeout_seconds: float = 300.0,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            cls.deploy_sync,
            project_path,
            provider=provider,
            preview=preview,
            timeout_seconds=timeout_seconds,
        )

    @classmethod
    def _run_deploy(
        cls,
        cfg: dict[str, Any],
        cwd: Path,
        timeout_seconds: float,
        *,
        preview: bool,
    ) -> dict[str, Any]:
        provider_name = str(cfg.get("name") or "unknown")
        if cfg.get("manual_only"):
            return {
                "success": False,
                "error": (
                    "Generic AWS deploy is not automated from chat. "
                    "Use SAM, CDK, CodeDeploy, or your CI pipeline with the AWS CLI configured."
                ),
                "provider": provider_name,
                "login_hint": cfg.get("login_hint"),
                "note": cfg.get("note"),
                "preview": preview,
            }

        if preview and cfg.get("deploy_shell") and not cfg.get("deploy_argv_preview"):
            return {
                "success": False,
                "error": (
                    "Preview deploy is not supported for this provider's git/shell flow "
                    "(e.g. Heroku). Use production deploy or the provider dashboard."
                ),
                "provider": provider_name,
                "preview": True,
            }

        shell_cmd = cfg.get("deploy_shell")
        if preview:
            argv = cfg.get("deploy_argv_preview")
            if not argv:
                argv = cfg.get("deploy_argv")
        else:
            argv = cfg.get("deploy_argv")

        try:
            if shell_cmd and not preview:
                proc = subprocess.run(
                    shell_cmd,
                    shell=True,
                    cwd=str(cwd),
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
            elif isinstance(argv, list) and argv:
                proc = subprocess.run(
                    argv,
                    shell=False,
                    cwd=str(cwd),
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
            else:
                return {
                    "success": False,
                    "error": "No deploy_argv or deploy_shell in registry entry",
                    "provider": provider_name,
                    "preview": preview,
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Deployment timed out after {int(timeout_seconds)} seconds",
                "provider": provider_name,
                "preview": preview,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc), "provider": provider_name, "preview": preview}

        out = (proc.stdout or "") + (proc.stderr or "")
        url_pattern = cfg.get("url_pattern")
        url = cls._extract_url(out, url_pattern if isinstance(url_pattern, str) else None)
        ok = proc.returncode == 0

        deploy_repr = shell_cmd if shell_cmd and not preview else " ".join(str(x) for x in (argv or []))

        err_tail = (proc.stderr or "").strip() if proc.stderr else None
        out_tail = (proc.stdout or "").strip() if proc.stdout else None

        result: dict[str, Any] = {
            "success": ok,
            "provider": provider_name,
            "command": deploy_repr,
            "stdout": out_tail[:12000] if out_tail else "",
            "stderr": err_tail[:8000] if err_tail else "",
            "url": url,
            "login_hint": cfg.get("login_hint"),
            "note": cfg.get("note"),
            "preview": preview,
        }
        if not ok:
            result["error"] = err_tail or out_tail or f"exit code {proc.returncode}"
        return result

    @staticmethod
    def _extract_url(text: str, pattern: str | None) -> str | None:
        if pattern:
            m = re.search(pattern, text)
            if m:
                u = m.group(0).rstrip(").,]}\"'")
                if not _is_noise_url(u):
                    return u
        generic = r"https?://[^\s\"'<>]+"
        matches = re.findall(generic, text)
        for u in matches:
            u2 = u.rstrip(").,]}\"'")
            if not _is_noise_url(u2):
                return u2
        return None


def _is_noise_url(url: str) -> bool:
    low = url.lower()
    return any(m in low for m in _LOCALHOST_MARKERS)
