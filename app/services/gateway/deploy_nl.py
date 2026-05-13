# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Gateway NL: generic CLI deploy (opt-in; privileged owners only)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.services.deployment.detector import DeploymentDetector
from app.services.deployment.executor import DeploymentExecutor
from app.services.deployment.project_layout import find_project_root
from app.services.gateway.context import GatewayContext
from app.services.host_executor_intent import (
    is_cancel_deploy_intent,
    is_reset_deploy_intent,
    parse_available_clouds_intent,
    parse_deploy_from_intent,
    parse_deploy_intent,
    parse_deploy_root_intent,
)
from app.services.user_capabilities import is_privileged_owner_for_web_mutations

_DEPLOY_DISPLAY: dict[str, str] = {
    "vercel": "Vercel",
    "railway": "Railway",
    "fly": "Fly.io",
    "netlify": "Netlify",
    "cloudflare": "Cloudflare (Wrangler)",
    "deno": "Deno Deploy",
    "gcloud": "Google Cloud (gcloud)",
    "heroku": "Heroku",
}

_PENDING_KEY = "nexa:deploy_choice_pending"
_PREF_KEY = "nexa:deploy_preferred_provider"
_PENDING_TTL_SEC = 900


def _resolve_deploy_folder_token(token: str) -> Path | None:
    """Strip quotes and resolve ``~`` / relative paths for deploy-root NL."""
    s = (token or "").strip().strip('"`\'')
    if not s:
        return None
    try:
        return Path(s).expanduser().resolve()
    except OSError:
        return None


def _deploy_workspace_root() -> str:
    s = get_settings()
    for attr in ("nexa_workspace_root", "nexa_command_work_root", "host_executor_work_root"):
        raw = str(getattr(s, attr, "") or "").strip()
        if raw:
            return raw
    return str(REPO_ROOT)


def _utc_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def _pending_expired(payload: dict[str, Any]) -> bool:
    exp = payload.get("expires_at")
    if exp is None:
        return False
    try:
        return float(exp) < _utc_ts()
    except (TypeError, ValueError):
        return False


def _get_pending(db: Session, user_id: str) -> dict[str, Any] | None:
    from app.repositories.memory_repo import MemoryRepository

    row = MemoryRepository().get(db, user_id, _PENDING_KEY)
    if not row:
        return None
    data = row.value_json or {}
    return dict(data) if isinstance(data, dict) else None


def _clear_pending(db: Session, user_id: str) -> None:
    from app.repositories.memory_repo import MemoryRepository

    row = MemoryRepository().get(db, user_id, _PENDING_KEY)
    if row:
        db.delete(row)
        db.commit()


def _save_pending(
    db: Session,
    user_id: str,
    *,
    options: list[str],
    workspace: str,
    preview: bool,
) -> None:
    from app.repositories.memory_repo import MemoryRepository

    MemoryRepository().upsert(
        db,
        user_id,
        _PENDING_KEY,
        {
            "options": options,
            "workspace": workspace,
            "preview": preview,
            "expires_at": _utc_ts() + _PENDING_TTL_SEC,
        },
        source="system",
    )


def _get_preferred_provider(db: Session, user_id: str) -> str | None:
    from app.repositories.memory_repo import MemoryRepository

    row = MemoryRepository().get(db, user_id, _PREF_KEY)
    if not row:
        return None
    data = row.value_json or {}
    if not isinstance(data, dict):
        return None
    p = str(data.get("provider") or "").strip()
    return p or None


def _set_preferred_provider(db: Session, user_id: str, provider: str) -> None:
    from app.repositories.memory_repo import MemoryRepository

    MemoryRepository().upsert(
        db,
        user_id,
        _PREF_KEY,
        {"provider": str(provider).strip()},
        source="user",
    )


def _pinned_provider_names(project_root: Path) -> list[str]:
    root_s = str(project_root)
    hints = DeploymentDetector.detect_by_file(root_s) + DeploymentDetector.detect_by_framework(root_s)
    names: list[str] = []
    seen: set[str] = set()
    for h in hints:
        n = str(h.get("name") or "").strip()
        if n and n not in seen:
            seen.add(n)
            names.append(n)
    return names


def _yaml_provider_slugs_ready(project_root: Path) -> list[str]:
    """Slugs from ``clouds.yaml`` whose rendered ``deploy_cmd`` argv0 exists on PATH."""
    from app.services.deployment.cloud_config import get_cloud_config
    from app.services.deployment.generic_deploy import deploy_argv0_on_path

    cc = get_cloud_config()
    pname = project_root.name
    ready: list[str] = []
    for slug, spec in cc.providers_map().items():
        cmd = str(spec.get("deploy_cmd") or "").strip()
        if cmd and deploy_argv0_on_path(cmd, project_name=pname):
            ready.append(slug)
    return sorted(set(ready))


def _deploy_slug_display(slug: str) -> str:
    from app.services.deployment.cloud_config import get_cloud_config

    y = get_cloud_config().get_provider(slug)
    if y and str(y.get("name") or "").strip():
        return str(y.get("name")).strip()
    return _DEPLOY_DISPLAY.get(slug, slug.replace("_", " ").title())


def _ordered_cli_names(project_root: Path) -> list[str]:
    """Slugs for CLIs on PATH with a deploy path (built-in registry and/or ``clouds.yaml``)."""
    avail = DeploymentDetector.detect_available(str(project_root))
    names: list[str] = []
    for c in avail:
        n = str(c.get("name") or "").strip()
        if not n or c.get("manual_only"):
            continue
        cfg = DeploymentDetector.get_registry(n) or c
        if cfg.get("manual_only"):
            continue
        if not (
            cfg.get("deploy_argv")
            or cfg.get("deploy_shell")
            or cfg.get("deploy_argv_preview")
        ):
            continue
        names.append(n)
    order = list(DeploymentDetector.PRIORITY)
    out: list[str] = []
    for k in order:
        if k in names:
            out.append(k)
    for k in names:
        if k not in out:
            out.append(k)
    seen = set(out)
    for k in _yaml_provider_slugs_ready(project_root):
        if k not in seen:
            out.append(k)
            seen.add(k)
    return out


def get_cloud_choices(project_root: Path) -> list[dict[str, Any]]:
    """Deployment targets: ``clouds.yaml`` overrides, else built-in registry."""
    from app.services.deployment.cloud_config import get_cloud_config

    cc = get_cloud_config()
    out: list[dict[str, Any]] = []
    for slug in _ordered_cli_names(project_root):
        yspec = cc.get_provider(slug)
        if yspec and str(yspec.get("deploy_cmd") or "").strip():
            disp = str(yspec.get("name") or "").strip() or _DEPLOY_DISPLAY.get(
                slug, slug.replace("_", " ").title()
            )
            out.append(
                {
                    "name": slug,
                    "display": disp,
                    "command": str(yspec.get("deploy_cmd") or "").strip(),
                }
            )
            continue
        cfg = DeploymentDetector.get_registry(slug)
        if not cfg or cfg.get("manual_only"):
            continue
        argv = cfg.get("deploy_argv") or cfg.get("deploy_argv_preview") or []
        shell = cfg.get("deploy_shell")
        cmd = " ".join(str(x) for x in argv) if isinstance(argv, list) and argv else (str(shell) if shell else slug)
        out.append(
            {
                "name": slug,
                "display": _DEPLOY_DISPLAY.get(slug, slug.replace("_", " ").title()),
                "command": cmd,
            }
        )
    return out


def install_instructions_text() -> str:
    return (
        "**No deployment tools found on this machine**\n\n"
        "Install at least one CLI, then try `deploy` again:\n\n"
        "• **Vercel:** `npm install -g vercel`\n"
        "• **Railway:** `brew install railway` (or see https://docs.railway.app/develop/cli)\n"
        "• **Fly.io:** https://fly.io/docs/hobbyists/install-flyctl/\n"
        "• **Netlify:** `npm install -g netlify-cli`\n"
        "• **Cloudflare:** `npm install -g wrangler`\n"
    )


def format_cloud_choice_prompt(project_root: Path) -> str:
    choices = get_cloud_choices(project_root)
    if not choices:
        return install_instructions_text()
    lines = [
        "**Which cloud should deploy this folder?**",
        "",
        f"_Deploy root:_ `{project_root}`",
        "",
    ]
    for i, c in enumerate(choices, 1):
        lines.append(f"{i}. **{c['display']}** (`{c['name']}`)")
    lines.append("")
    lines.append("Reply with the **number** or **`deploy to <name>`**.")
    lines.append("Say **`cancel`** to abort, or **`reset deploy`** to clear this prompt.")
    lines.append("To use a different folder: **`change deploy root to /path`** (while this prompt is open).")
    lines.append("_Your choice is remembered for the next plain `deploy`._")
    return "\n".join(lines)


def format_available_clouds_reply(project_root: Path) -> str:
    choices = get_cloud_choices(project_root)
    if not choices:
        return "**Available deployment targets:** none detected.\n\n" + install_instructions_text()
    lines = ["**Available deployment targets (installed CLIs):**", ""]
    for c in choices:
        lines.append(f"• **{c['display']}** — `{c['name']}`")
    lines.append("")
    lines.append("Say **`deploy`** to pick (or use a saved default), or **`deploy to <name>`**.")
    return "\n".join(lines)


def parse_deploy_choice_reply(text: str, options: list[str]) -> str | None:
    """Match replies like ``2``, ``vercel``, or ``deploy to railway`` against pending options."""
    if not options:
        return None
    line = text.strip().splitlines()[0].strip()
    low = line.lower()

    m = re.match(r"(?is)^deploy\s+to\s+([\w.-]+)\s*$", line)
    if m:
        raw_p = m.group(1).strip().lower()
        if raw_p in options:
            return raw_p
        from app.services.deployment.detector import _normalize_provider

        norm = _normalize_provider(raw_p)
        if norm and norm in options:
            return norm

    m2 = re.match(r"^(\d{1,2})\s*$", line)
    if m2:
        idx = int(m2.group(1)) - 1
        if 0 <= idx < len(options):
            return options[idx]

    if low in options:
        return low
    return None


def _resolve_provider_for_generic_deploy(
    db: Session,
    uid: str,
    *,
    project_root: Path,
    parsed_provider: str | None,
) -> tuple[str | None, bool]:
    """
    Returns ``(provider_slug_or_none, needs_prompt)``.
    When ``needs_prompt`` is True, caller should show cloud-choice UI and save pending state.
    """
    if parsed_provider:
        return parsed_provider.strip().lower(), False

    pinned = _pinned_provider_names(project_root)
    if len(pinned) == 1:
        return pinned[0], False

    ordered = _ordered_cli_names(project_root)
    if not ordered:
        return None, False

    pref = _get_preferred_provider(db, uid)
    if pref and pref in ordered:
        return pref, False

    if len(pinned) > 1:
        opts = [x for x in ordered if x in pinned] or ordered
        if len(opts) > 1:
            return None, True
        if len(opts) == 1:
            return opts[0], False

    if len(ordered) == 1:
        return ordered[0], False
    if len(ordered) > 1:
        return None, True
    return None, False


def try_gateway_deploy_turn(
    gctx: GatewayContext,
    raw_message: str,
    db: Session,
) -> dict[str, Any] | None:
    """Run generic deploy when intent matches and settings + owner gate pass."""
    raw = (raw_message or "").strip()
    uid = (gctx.user_id or "").strip()
    if not raw or not uid:
        return None

    settings = get_settings()
    if not bool(getattr(settings, "nexa_generic_deploy_enabled", False)):
        return None
    if not is_privileged_owner_for_web_mutations(db, uid):
        return None

    from app.services.gateway.runtime import gateway_finalize_chat_reply

    pending = _get_pending(db, uid)
    if pending and _pending_expired(pending):
        _clear_pending(db, uid)
        pending = None

    if is_reset_deploy_intent(raw):
        _clear_pending(db, uid)
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(
                "**Deploy state reset.**\n\nYou can start again with `deploy` or `deploy to <provider>`.",
                source="deploy_reset",
                user_text=raw,
            ),
            "intent": "deploy_reset",
        }

    if pending and is_cancel_deploy_intent(raw):
        _clear_pending(db, uid)
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(
                "**Deployment cancelled.**\n\nSay `deploy` when you want to try again.",
                source="deploy_cancelled",
                user_text=raw,
            ),
            "intent": "deploy_cancelled",
        }

    workspace0 = _deploy_workspace_root()
    root0 = find_project_root(Path(workspace0))
    if (
        parse_available_clouds_intent(raw)
        and parse_deploy_intent(raw) is None
        and parse_deploy_from_intent(raw) is None
    ):
        body = format_available_clouds_reply(root0)
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(body.strip(), source="deploy_available_targets", user_text=raw),
            "intent": "available_clouds",
        }

    from_int = parse_deploy_from_intent(raw)
    if from_int:
        tok = str(from_int.get("folder") or "")
        pth = _resolve_deploy_folder_token(tok)
        if pth is None or not pth.is_dir():
            return {
                "mode": "chat",
                "text": gateway_finalize_chat_reply(
                    (
                        f"**Folder not found**\n\n`{tok}` is not an existing directory.\n\n"
                        + install_instructions_text()
                    ).strip(),
                    source="deploy_from_bad_path",
                    user_text=raw,
                ),
                "intent": "deploy_root_error",
            }
        _clear_pending(db, uid)
        pending = None
        workspace_start = str(find_project_root(pth))
        parsed: dict[str, Any] | None = {
            "intent": "deploy",
            "deploy_type": "deploy",
            "provider": None,
            "raw_text": raw,
        }
    else:
        workspace_start = _deploy_workspace_root()
        parsed = parse_deploy_intent(raw)

    if parsed and parsed.get("provider"):
        _clear_pending(db, uid)

    if parsed is None:
        if not pending:
            return None
        root_int = parse_deploy_root_intent(raw)
        if root_int:
            tok = str(root_int.get("folder") or "")
            new_base = _resolve_deploy_folder_token(tok)
            opts = list(pending.get("options") or [])
            preview_b = bool(pending.get("preview"))
            cur_ws = str(pending.get("workspace") or _deploy_workspace_root())
            cur_root = find_project_root(Path(cur_ws))
            if new_base is None or not new_base.is_dir():
                body = (
                    f"**Folder not found**\n\n`{tok}` is not a directory.\n\n"
                    + format_cloud_choice_prompt(cur_root)
                )
                return {
                    "mode": "chat",
                    "text": gateway_finalize_chat_reply(
                        body.strip(),
                        source="deploy_root_error_pending",
                        user_text=raw,
                    ),
                    "intent": "deploy_root_error_pending",
                }
            new_root = find_project_root(new_base)
            _save_pending(db, uid, options=opts, workspace=str(new_root), preview=preview_b)
            body = "**Deploy root updated.**\n\n" + f"New root: `{new_root}`\n\n" + format_cloud_choice_prompt(new_root)
            return {
                "mode": "chat",
                "text": gateway_finalize_chat_reply(
                    body.strip(),
                    source="deploy_root_changed_pending",
                    user_text=raw,
                ),
                "intent": "deploy_root_changed_pending",
            }
        choice = parse_deploy_choice_reply(raw, list(pending.get("options") or []))
        if not choice:
            opts = list(pending.get("options") or [])
            lines = [
                "**Pick a cloud for this deploy**",
                "",
                "Reply with the **number** or say **`deploy to <tool>`**.",
                "Say **`cancel`** to abort, or **`reset deploy`** to clear state.",
                "You can say **`change deploy root to /path`** to point at another folder first.",
                "",
            ]
            for i, name in enumerate(opts, 1):
                disp = _deploy_slug_display(name)
                lines.append(f"{i}. **{disp}** (`{name}`)")
            return {
                "mode": "chat",
                "text": gateway_finalize_chat_reply("\n".join(lines), source="deploy_choice_remind", user_text=raw),
                "intent": "deploy_choice_pending",
            }
        workspace = str(pending.get("workspace") or _deploy_workspace_root())
        preview = bool(pending.get("preview"))
        _clear_pending(db, uid)
        timeout = float(getattr(settings, "nexa_deploy_timeout_seconds", 300.0) or 300.0)
        root = find_project_root(Path(workspace))
        result = DeploymentExecutor.deploy_sync(
            str(root),
            provider=choice,
            preview=preview,
            timeout_seconds=timeout,
        )
        return _finalize_deploy_reply(raw, result=result, db=db, uid=uid, explicit_provider=choice)

    assert parsed is not None

    timeout = float(getattr(settings, "nexa_deploy_timeout_seconds", 300.0) or 300.0)
    root = find_project_root(Path(workspace_start))
    preview = str(parsed.get("deploy_type") or "deploy") == "deploy_preview"
    explicit = str(parsed.get("provider") or "").strip() or None

    installed_slugs = _ordered_cli_names(root)
    if explicit is None and not installed_slugs:
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(
                install_instructions_text().strip(),
                source="deploy_no_cli",
                user_text=raw,
            ),
            "intent": "deploy_no_cli",
        }

    need_prompt = False
    chosen: str | None = explicit

    if not explicit:
        chosen, need_prompt = _resolve_provider_for_generic_deploy(
            db,
            uid,
            project_root=root,
            parsed_provider=None,
        )

    if need_prompt:
        opts = _ordered_cli_names(root)
        if len(opts) <= 1:
            chosen = opts[0] if opts else None
        else:
            _save_pending(db, uid, options=opts, workspace=str(root), preview=preview)
            return {
                "mode": "chat",
                "text": gateway_finalize_chat_reply(
                    format_cloud_choice_prompt(root).strip(),
                    source="deploy_choice",
                    user_text=raw,
                ),
                "intent": "deploy_choice_required",
            }

    result = DeploymentExecutor.deploy_sync(
        str(root),
        provider=chosen,
        preview=preview,
        timeout_seconds=timeout,
    )
    return _finalize_deploy_reply(
        raw,
        result=result,
        db=db,
        uid=uid,
        explicit_provider=explicit or chosen,
    )


def _finalize_deploy_reply(
    raw: str,
    *,
    result: dict[str, Any],
    db: Session,
    uid: str,
    explicit_provider: str | None,
) -> dict[str, Any]:
    from app.services.gateway.runtime import gateway_finalize_chat_reply

    if result.get("success"):
        prov = str(result.get("provider") or explicit_provider or "").strip()
        if prov:
            _set_preferred_provider(db, uid, prov)

        url = result.get("url") or "(see CLI output)"
        preview_note = " **(Preview)**" if result.get("preview") else ""
        pr_root = result.get("project_root") or ""
        nfiles = result.get("deployed_files")
        branch = result.get("git_branch")
        commit = result.get("git_commit")
        remote = result.get("git_remote")

        body = (
            f"✅ **DEPLOYMENT COMPLETE**{preview_note}\n\n"
            f"• **Provider:** **{result.get('provider')}**\n"
            f"• **URL:** {url}\n"
            f"• **Command:** `{result.get('command')}`\n"
        )
        if pr_root:
            body += f"• **Project root:** `{pr_root}`\n"
        if nfiles is not None:
            body += f"• **Files under root:** {nfiles}\n"
        if branch:
            body += f"• **Git branch:** `{branch}`\n"
        if commit:
            body += f"• **Git commit:** `{commit}`\n"
        if remote:
            body += f"• **Git remote:** `{remote}`\n"
        body += "\n💡 Share the URL with your team!"
        if result.get("stdout"):
            body += f"\n```\n{str(result.get('stdout'))[:4000]}\n```\n"
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(
                body.strip(),
                source="generic_deploy",
                user_text=raw,
            ),
            "intent": "deployment_complete",
            "deployment": result,
        }

    avail = result.get("available_detected") or []
    cfg_detect = result.get("config_detected") or []
    hint = result.get("login_hint")
    suggestion = result.get("suggestion") or ""
    err = result.get("error") or "Unknown error"
    lines = (
        f"❌ **DEPLOYMENT FAILED**\n\n"
        f"**Error:** {err}\n\n"
        f"💡 **PATH CLIs:** {avail if avail else 'none'}\n"
    )
    if cfg_detect:
        lines += f"📁 **Config hints:** {', '.join(cfg_detect)}\n"
    if suggestion:
        lines += f"\n{suggestion}\n"
    if hint:
        lines += f"\nTry: `{hint}`\n"
    if avail:
        lines += "\nYou can also say `deploy to vercel` (or another installed tool).\n"
    else:
        lines += "\n" + install_instructions_text()
    return {
        "mode": "chat",
        "text": gateway_finalize_chat_reply(lines.strip(), source="generic_deploy_fail", user_text=raw),
        "intent": "deployment_failed",
        "deployment": result,
    }


__all__ = [
    "format_available_clouds_reply",
    "format_cloud_choice_prompt",
    "get_cloud_choices",
    "install_instructions_text",
    "parse_deploy_choice_reply",
    "try_gateway_deploy_turn",
]
