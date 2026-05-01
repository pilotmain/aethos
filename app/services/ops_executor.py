"""
Whitelisted infrastructure actions for Nexa Ops. No user-controlled argv beyond allowlisted keys.
Execution uses `Project` → registered `OpsProvider` (not NEXA_OPS_* alone).
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.project import Project
from app.services.handoff_paths import PROJECT_ROOT
from app.services.ops import provider_registry
from app.services.ops.ops_project_context import resolve_ops_project, validate_project_repo
from app.services.ops.provider_registry import get_provider
from app.services.ops_actions import OPS_ACTIONS
from app.services.project_registry import project_services
from app.services.safe_llm_gateway import sanitize_text
from app.services.worker_heartbeat import build_dev_health_report

MAX_OUT = 1000
_DRY = "1"
SECRETS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk-[A-Za-z0-9-]{8,}"), "[token]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.I), "Bearer [redacted]"),
    (re.compile(r'(?i)(api_?key|token|password|secret)\s*[:=]\s*(\S+)', re.I), r"\1=[redacted]"),
]

ROOT = Path(PROJECT_ROOT).resolve()
_COMPOSE = os.environ.get("NEXA_OPS_DOCKER_COMPOSE", str(ROOT / "docker-compose.yml"))
_LOG_FILE_MAP = {
    "api": os.environ.get("NEXA_OPS_LOG_FILE_API", ""),
    "bot": os.environ.get("NEXA_OPS_LOG_FILE_BOT", ""),
    "worker": os.environ.get("NEXA_OPS_LOG_FILE_WORKER", ""),
}


def sanitize_log_text(s: str, max_len: int = MAX_OUT) -> str:
    r = s or ""
    for pat, rep in SECRETS_PATTERNS:
        r = pat.sub(rep, r)
    r = sanitize_text(r)[: max_len * 2]
    return (r or "")[:max_len]


def which(name: str) -> bool:
    from shutil import which as w

    return w(name) is not None


def _is_dry() -> bool:
    return (os.environ.get("NEXA_OPS_DRY_RUN", _DRY) or "1") != "0"


def _subprocess_check(
    argv: list[str], *, cwd: Path | str, timeout: int = 120
) -> str:
    try:
        p = subprocess.run(  # noqa: S603
            argv,
            cwd=Path(cwd).resolve(),
            text=True,
            capture_output=True,
            timeout=timeout,
            env={**os.environ, "NEXA_OPS_CHILD": "1"},
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"(subprocess: {e!s})"[:500]
    out = (p.stdout or "") + (("\nSTDERR:\n" + p.stderr) if p.stderr else "")
    if p.returncode not in (0,):
        out = f"exit {p.returncode}\n" + (out or "")[:4000]
    return (out or "")[:8000]


def _norm_log_service(s: str) -> str:
    t = (s or "api").lower()
    if t in ("app", "web"):
        t = "api"
    return t


def _docker_logs_service_cwd(
    work_root: Path, service: str, cfile: str | None
) -> str:
    s = _norm_log_service(service)
    allowed = frozenset(
        {
            "api",
            "bot",
            "worker",
            "db",
            "postgres",
            "redis",
        }
    )
    if s not in allowed:
        s = "api"
    docker_service = s if s not in ("postgres",) else "db"
    if os.environ.get("NEXA_OPS_ENABLE_DOCKER_LOGS") != "1":
        p = _LOG_FILE_MAP.get(s) or _LOG_FILE_MAP.get("api") or ""
        if p and Path(p).is_file():
            try:
                raw = Path(p).read_text(encoding="utf-8", errors="replace")[-8000:]
                return f"**Last file tail ({s})**:\n{sanitize_log_text(raw)}"
            except OSError as e:
                return f"Nexa: could not read {p}: {e!s}\n"
        return (
            f"Nexa Ops — logs for `{s}`\n\n"
            "Set `NEXA_OPS_LOG_FILE_API` / `NEXA_OPS_LOG_FILE_BOT` (or set "
            "`NEXA_OPS_ENABLE_DOCKER_LOGS=1` with a valid `docker-compose` in the project `repo_path`)."
        )
    cf = cfile or _COMPOSE
    cfp = work_root / "docker-compose.yml" if not Path(cf).is_file() else Path(cf)
    if not cfp.is_file() and not Path(_COMPOSE).is_file():
        return f"Nexa: compose file not found for this project (looked under `{work_root!s}`). Set NEXA_OPS_DOCKER_COMPOSE or add docker-compose.yml."
    use_f = cfp if cfp.is_file() else Path(_COMPOSE)
    argv = [
        "docker",
        "compose",
        "-f",
        str(use_f),
        "logs",
        docker_service,
        "--tail",
        "100",
    ]
    return (
        f"**docker compose logs — {docker_service}** (read-only, truncated)\n"
        f"{sanitize_log_text(_subprocess_check(argv, cwd=work_root, timeout=90), max_len=2000)}"
    )


def _maybe_logs_unknown_service(
    project: Project,
    svc: str,
) -> str | None:
    sp = [str(x).lower() for x in (project_services(project) or [])]
    if not sp or svc in sp or svc in ("all", "postgres", "app"):
        return None
    return (
        f"I do not have service `{svc!r} for {project.display_name}.\n\n**Known services:**\n"
        + ", ".join(sp)
    )


def _provider_status_for_project(
    prov: Any,
    project: Project,
    pld: dict[str, Any],
) -> str:
    key = (getattr(prov, "key", None) or getattr(prov, "name", "")).lower()
    if key == "local_docker":
        return ""
    return (
        f"\n\n**Provider `{getattr(prov, 'name', 'cloud')}` (status, truncated)**\n"
        f"{sanitize_log_text(str(prov.execute('status', project, pld) or ''), 1500)}"
    )


def set_env_var(key: str, value: str) -> str:
    k, v = (key or "")[:64], (value or "")[:500]
    if not re.match(r"^[A-Z_][A-Z0-9_]*$", k):
        return f"Nexa: only `KEY=value` with uppercase safe names is allowed (got {k!r})."
    return (
        f"Nexa Ops will not write secrets or cloud env from chat. If approved on the host, set `{k}` "
        f"in your provider dashboard or secret manager. Value length: {len(v)} chars (not echoed for safety)."
    )


def _jobs_view(db: Session, app_user_id: str) -> str:
    from app.services.agent_job_service import AgentJobService
    from app.services.telegram_dev_ux import format_job_row_short

    js = AgentJobService()
    rows = js.list_jobs(db, app_user_id, limit=5)
    if not rows:
        return "No jobs yet in Nexa."
    return "Recent jobs:\n\n" + "\n\n".join(format_job_row_short(j) for j in rows)[:10_000]


def _queue_view(db: Session, app_user_id: str) -> str:
    from app.services.agent_job_service import AgentJobService
    from app.services.telegram_dev_ux import format_job_row_short

    rows = AgentJobService().list_jobs(db, app_user_id, limit=25)
    de = [j for j in rows if (j.worker_type or "") == "dev_executor"]
    if not de:
        return "No dev jobs in the recent list."
    return "Queue (recent dev jobs):\n\n" + "\n\n".join(
        format_job_row_short(x) for x in de[:8]
    )[:10_000]


def execute_action(
    action_name: str,
    payload: dict[str, Any],
    *,
    db: Session | None = None,
    app_user_id: str | None = None,
    active_project_key: str | None = None,
) -> str:
    if action_name not in OPS_ACTIONS:
        return "Nexa: this operation is not in the v1 allowlist."
    pld0 = dict(payload or {})

    if action_name in ("queue", "jobs") and db is not None and app_user_id is not None:
        if action_name == "queue":
            return _queue_view(db, app_user_id)
        return _jobs_view(db, app_user_id)
    if action_name in ("queue", "jobs"):
        return "Nexa: jobs/queue need an active user context on this run."

    if db is None:
        return "Nexa: this op needs a database session (set up projects first)."

    try:
        proj, err = resolve_ops_project(
            db,
            pld0,
            active_project_key=active_project_key,
        )
        if err:
            return err
        if proj is None:
            return "Nexa: no project to run against. Use `/project add` or the default `nexa` seed."
        v_err = validate_project_repo(proj)
        if v_err and action_name not in (
            "set_env_var",
            "rollback",
            "health",
            "status",
        ):
            return v_err

        prov = get_provider(proj.provider_key)
        pkey = ""
        if prov is not None:
            pkey = (getattr(prov, "key", None) or getattr(prov, "name", "") or "").lower()
        if prov is None and action_name in (
            "health",
            "status",
            "logs",
            "deploy_staging",
            "deploy_production",
            "restart_service",
            "rollback",
        ):
            return (
                f"Nexa: provider `{proj.provider_key}` is not registered. "
                f"Add it in the registry or set `Project.provider_key`. "
                f"Available: {', '.join(provider_registry.list_provider_names())}."
            )

        if action_name == "set_env_var":
            text = set_env_var(str(pld0.get("key", "")), str(pld0.get("value", "")))
            if prov is not None and not _is_dry():
                text = str(prov.execute("set_env_var", proj, pld0) or text)[:10_000]
            return text

        if action_name == "status":
            hdr = (
                f"**{proj.display_name}** (`{proj.key}`) · **Provider** `{proj.provider_key}`\n\n"
            )
            if _is_dry():
                return (
                    hdr
                    + "Nexa Ops — **status** (dry run). Set `NEXA_OPS_DRY_RUN=0` on the worker to run "
                    "`docker compose ps` / `railway status` for real."
                )[:10_000]
            if prov is None:
                return (
                    hdr
                    + "Nexa: no provider for this project — cannot read deployment status. "
                    "Set `Project.provider_key` to a registered ops provider."
                )[:10_000]
            raw = str(prov.execute("status", proj, pld0) or "").strip()
            if not raw:
                raw = (
                    "(no output from provider status; ensure Docker / `railway` CLI is on PATH on the worker host.)"
                )
            return (hdr + f"**Nexa Ops — status**\n{sanitize_log_text(raw, 2800)}")[:10_000]

        if action_name == "health":
            h = (build_dev_health_report() or "").strip()
            if not h:
                body = "Nexa Ops — worker status unknown (no heartbeat on this host). See `/dev health`."
            else:
                body = f"**Nexa Ops — health**\n{sanitize_log_text(h, 1200)}"
            body = f"**{proj.display_name}** (`{proj.key}`) · provider `{proj.provider_key}`\n\n" + body
            status_on = (os.environ.get("NEXA_OPS_STATUS_VIA", "") or "").lower() in (
                "1", "true", "yes", "provider",
            )
            if prov is not None and status_on and not _is_dry():
                if pkey in ("local_docker", "local", "docker"):
                    body = body + "\n\n" + str(prov.execute("status", proj, pld0) or "")[:1800]
                else:
                    body = body + _provider_status_for_project(prov, proj, pld0)
            return body

        if action_name == "logs":
            svc = str(pld0.get("service") or "api")
            u_msg = _maybe_logs_unknown_service(proj, svc)
            if u_msg:
                return u_msg
            cfile = os.environ.get("NEXA_OPS_DOCKER_COMPOSE")
            src = (os.environ.get("NEXA_OPS_LOGS_SOURCE", "file") or "file").lower()
            if src in ("1", "true", "yes", "provider", "cloud"):
                if prov is None:
                    return "Nexa: no provider for this project; cannot use provider logs."
                raw = str(prov.execute("logs", proj, pld0) or "")
                return (
                    f"Logs for **{proj.display_name}** / **{svc}**:\n\n**Provider (`{pkey or proj.provider_key}`)**\n"
                    f"{sanitize_log_text(raw, 2000)}"
                )
            wr = Path((proj.repo_path or str(ROOT))).resolve()
            inner = _docker_logs_service_cwd(wr, svc, cfile)
            return f"Logs for **{proj.display_name}** / **{svc}**:\n\n{inner}"

        if action_name in ("deploy_staging", "deploy_production", "rollback", "restart_service"):
            if _is_dry():
                if action_name in ("deploy_staging", "deploy_production"):
                    label = "Production" if action_name == "deploy_production" else "Staging"
                    return (
                        f"🚀 **Nexa Ops — {label} deploy (dry run)**\n\n**Project:** {proj.display_name} "
                        f"(`{proj.key}`) · **Provider:** `{proj.provider_key}`\n"
                        f"No deploy was run. Set `NEXA_OPS_DRY_RUN=0` on the worker after in-chat approval."
                    )
                if action_name == "rollback":
                    return f"↩ **Rollback (dry run)** for `{proj.key}` — no change executed on the host."
                return (
                    f"**Restart (dry run)** for `{proj.key}` — not executed. Set `NEXA_OPS_DRY_RUN=0` to allow."
                )
            if prov is None:
                return "Nexa: provider missing for this project (cannot run)."
            if pkey == "railway" and action_name in (
                "deploy_staging",
                "deploy_production",
                "restart_service",
            ) and not which("railway"):
                return (
                    "Nexa: the `railway` CLI is not on PATH for the worker. Install and log in, or switch provider."
                )
            raw = str(prov.execute(action_name, proj, pld0) or "")
            hdr = f"**{proj.display_name}** (`{proj.key}`) · **Provider** `{pkey or proj.provider_key}`\n\n"
            if action_name == "deploy_staging":
                return hdr + f"🚀 **Deploy (staging)**\n{sanitize_log_text(raw, 2500)}"
            if action_name == "deploy_production":
                return hdr + f"⛔ **Deploy (production)**\n{sanitize_log_text(raw, 2500)}"
            if action_name == "restart_service":
                return hdr + f"**Restart (provider)**\n{sanitize_log_text(raw, 2000)}"
            return hdr + sanitize_log_text(raw, 2000)
    except Exception:  # noqa: BLE001
        return "Something went wrong while executing this action. Check logs or try again in Nexa."
    return f"Nexa: unhandled op `{action_name}`."
