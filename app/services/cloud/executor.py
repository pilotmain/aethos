# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Universal cloud CLI executor (sync) — deploy / logs with deployment session tracking.

Railway/Vercel specialized flows stay in :mod:`app.services.infra.railway` /
:class:`~app.services.infra.vercel.VercelClient`; this module covers **other** registry providers.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time
from typing import Any

from app.services.cloud.registry import CloudProvider, get_provider_registry
from app.services.deployment.session import get_deployment_session
from app.services.infra.cli_env import cli_auth_env
from app.services.infra.railway import RailwayClient

logger = logging.getLogger(__name__)

# CLIs whose logs commands must not receive a stray numeric tail from the generic fallback.
_CLI_LOGS_BASE_ONLY = frozenset({
    "kubectl",
    "oc",
    "terraform",
    "pulumi",
    "doctl",
    "render",
    "koyeb",
    "northflank",
    "cycle",
    "porter",
    "zeabur",
    "adaptable",
    "kinsta",
    "platform",
    "cleavr",
})


class UniversalCloudExecutor:
    """Run provider CLI commands with merged auth env (tokens from process environment)."""

    def deploy(
        self,
        provider: CloudProvider,
        *,
        extra_env: dict[str, str] | None = None,
        timeout_sec: int = 180,
    ) -> dict[str, Any]:
        cmd = list(provider.deploy_command or [])
        if not cmd:
            return {
                "success": False,
                "error": "No deploy_command configured for this provider.",
                "provider": provider.name,
            }
        exe = cmd[0]
        if not shutil.which(exe):
            hint = provider.install_command or "Install the provider CLI and ensure it is on PATH."
            return {
                "success": False,
                "error": f"`{exe}` not found on PATH. {hint}",
                "provider": provider.name,
            }
        env = cli_auth_env()
        if extra_env:
            for k, v in extra_env.items():
                if k and v is not None:
                    env[str(k).strip()] = str(v).strip()
        try:
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=int(timeout_sec),
                env=env,
            )
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Deploy timed out after {timeout_sec}s",
                "provider": provider.name,
            }
        except OSError as exc:
            return {"success": False, "error": str(exc), "provider": provider.name}

        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        ok = r.returncode == 0
        blob = "\n".join(x for x in (out, err) if x)
        url = RailwayClient._first_http_url(blob)
        return {
            "success": ok,
            "output": out or "(no stdout)",
            "stderr": err,
            "error": None if ok else (err or out or f"exit {r.returncode}")[:8000],
            "provider": provider.name,
            "url": url,
        }

    def get_logs_text(self, provider: CloudProvider, *, tail: int = 100, timeout_sec: int = 90) -> str:
        """Best-effort ``logs`` subprocess for the provider."""
        base = list(provider.logs_command or [])
        if not base:
            return ""
        exe = base[0]
        if not shutil.which(exe):
            return ""
        env = cli_auth_env()
        variants: list[list[str]] = []
        low = " ".join(base).lower()
        if "railway" in low and "logs" in low:
            variants.extend(
                [
                    base + ["--tail", str(tail)],
                    base + ["--lines", str(tail)],
                    base,
                ]
            )
        elif base[0] in {"fly", "heroku"}:
            variants.append(base + ["--tail"])
            variants.append(base)
        elif base[0] == "aws":
            variants.append(base)
        elif base[0] == "gcloud":
            variants.append(base + ["--limit", str(min(tail, 500))])
            variants.append(base)
        elif base[0] == "wrangler":
            variants.append(base)
        elif base[0] == "netlify":
            variants.append(base + ["--tail"])
            variants.append(base)
        elif base[0] == "az":
            variants.append(base)
        elif base[0] == "vercel":
            variants.append(base + ["--limit", str(tail)])
            variants.append(base)
        elif base[0] in _CLI_LOGS_BASE_ONLY:
            variants.append(base)
        else:
            variants.append(base + [str(tail)])
            variants.append(base)

        last = ""
        for argv in variants:
            try:
                r = subprocess.run(
                    argv,
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                    env=env,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                logger.debug("logs argv=%s err=%s", argv, exc)
                continue
            blob = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
            if blob:
                last = blob
            if r.returncode == 0 and blob:
                return blob[:12000]
        return last[:12000]

    def _collect_logs_background(self, session_id: int, provider_name: str) -> None:
        reg = get_provider_registry()
        prov = reg.get(provider_name)
        if prov is None or not prov.logs_command:
            return

        def worker() -> None:
            store = get_deployment_session()
            for _ in range(30):
                time.sleep(10)
                logs = self.get_logs_text(prov, tail=120)
                if logs:
                    store.store_logs(session_id, logs)
                low = (logs or "").lower()
                if any(x in low for x in ("error", "fatal", "failed", "npm err", "traceback")):
                    break

        threading.Thread(
            target=worker,
            daemon=True,
            name=f"cloud-log-tail-{provider_name}-{session_id}",
        ).start()

    def deploy_with_tracking(
        self,
        *,
        chat_id: str,
        provider: CloudProvider,
        extra_env: dict[str, str] | None = None,
        metadata: dict[str, Any] | None = None,
        timeout_sec: int = 180,
    ) -> dict[str, Any]:
        """Deploy + persist session + optional background log tail (Phase 52 / 52b)."""
        store = get_deployment_session()
        cid = (chat_id or "").strip()
        sid: int | None = None
        if cid:
            meta = dict(metadata or {})
            meta["executor"] = "universal"
            sid = store.start_session(cid, provider.name, meta)

        res = self.deploy(provider, extra_env=extra_env, timeout_sec=timeout_sec)
        out = dict(res)
        if sid is None:
            return out

        if res.get("success"):
            blob = (res.get("output") or "") + "\n" + (res.get("stderr") or "")
            url = res.get("url") or RailwayClient._first_http_url(blob)
            logs_url = RailwayClient._first_http_url(blob, substr="railway.app") or url
            store.update_session(
                sid,
                "success",
                url=url,
                logs_url=logs_url,
                set_completed=True,
                clear_error=True,
            )
            self._collect_logs_background(sid, provider.name)
        else:
            err = (res.get("error") or res.get("stderr") or "unknown error")[:8000]
            store.update_session(sid, "failed", error=err, set_completed=True)

        out["deployment_session_id"] = sid
        return out


_executor: UniversalCloudExecutor | None = None


def get_universal_cloud_executor() -> UniversalCloudExecutor:
    global _executor
    if _executor is None:
        _executor = UniversalCloudExecutor()
    return _executor


__all__ = ["UniversalCloudExecutor", "get_universal_cloud_executor"]
