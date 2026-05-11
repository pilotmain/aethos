"""Run deployment using detected CLIs (subprocess; gateway-safe synchronous API)."""

from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.services.deployment.detector import DeploymentDetector, _normalize_provider


class DeploymentExecutor:
    """Execute one deployment attempt using registry-defined commands."""

    @classmethod
    def deploy_sync(
        cls,
        project_path: str,
        *,
        provider: str | None = None,
        timeout_seconds: float = 300.0,
    ) -> dict[str, Any]:
        """
        Deploy from ``project_path`` using an installed CLI.

        When ``provider`` is set, only that provider is attempted (if binary exists).
        Otherwise file hints are tried first, then available CLIs in :attr:`DeploymentDetector.PRIORITY` order.

        **Note:** Many providers need prior login and project linking; failures surface in stderr.
        """
        root = Path(project_path).expanduser().resolve()
        if not root.is_dir():
            return {
                "success": False,
                "error": f"Not a directory: {root}",
                "provider": provider,
            }

        if provider:
            norm = _normalize_provider(provider)
            cfg = DeploymentDetector.get_registry(norm or "")
            if not cfg:
                return {"success": False, "error": f"Unknown provider: {provider}", "provider": provider}
            bin_name = str(cfg.get("binary") or "")
            if not shutil.which(bin_name):
                return {
                    "success": False,
                    "error": f"CLI not on PATH: {bin_name}",
                    "provider": cfg["name"],
                    "login_hint": cfg.get("login_hint"),
                }
            return cls._run_deploy(cfg, root, timeout_seconds)

        file_hints = DeploymentDetector.detect_by_file(str(root))
        available = DeploymentDetector.detect_available()

        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        for c in file_hints + available:
            name = str(c.get("name") or "")
            if name and name not in seen:
                seen.add(name)
                candidates.append(c)

        if not candidates:
            return {
                "success": False,
                "error": "No deployment CLI found on PATH (install vercel, railway, flyctl, netlify, etc.).",
                "available_detected": [],
            }

        errors: list[str] = []
        for cfg in candidates:
            name = str(cfg.get("name") or "unknown")
            res = cls._run_deploy(cfg, root, timeout_seconds)
            if res.get("success"):
                return res
            err = str(res.get("error") or res.get("stderr") or "failed")
            errors.append(f"{name}: {err[:200]}")

        return {
            "success": False,
            "error": "; ".join(errors) if errors else "All deployment attempts failed.",
            "available_detected": [str(c.get("name")) for c in candidates],
        }

    @classmethod
    async def deploy(
        cls,
        project_path: str,
        *,
        provider: str | None = None,
        timeout_seconds: float = 300.0,
    ) -> dict[str, Any]:
        """Async wrapper (thread offload) for callers that already use asyncio."""
        return await asyncio.to_thread(
            cls.deploy_sync,
            project_path,
            provider=provider,
            timeout_seconds=timeout_seconds,
        )

    @classmethod
    def _run_deploy(
        cls,
        cfg: dict[str, Any],
        cwd: Path,
        timeout_seconds: float,
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
            }
        shell_cmd = cfg.get("deploy_shell")
        argv = cfg.get("deploy_argv")

        try:
            if shell_cmd:
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
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Deployment timed out after {int(timeout_seconds)} seconds",
                "provider": provider_name,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc), "provider": provider_name}

        out = (proc.stdout or "") + (proc.stderr or "")
        url_pattern = cfg.get("url_pattern")
        url = cls._extract_url(out, url_pattern if isinstance(url_pattern, str) else None)
        ok = proc.returncode == 0

        deploy_repr = shell_cmd if shell_cmd else " ".join(str(x) for x in (argv or []))

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
        }
        if not ok:
            result["error"] = err_tail or out_tail or f"exit code {proc.returncode}"
        return result

    @staticmethod
    def _extract_url(text: str, pattern: str | None) -> str | None:
        if pattern:
            m = re.search(pattern, text)
            if m:
                return m.group(0).rstrip(").,]}\"'")
        generic = r"https?://[^\s\"'<>]+"
        matches = re.findall(generic, text)
        return matches[0].rstrip(").,]}\"'") if matches else None
