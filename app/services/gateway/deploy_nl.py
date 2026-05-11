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
from app.services.host_executor_intent import parse_deploy_intent
from app.services.user_capabilities import is_privileged_owner_for_web_mutations

_PENDING_KEY = "nexa:deploy_choice_pending"
_PREF_KEY = "nexa:deploy_preferred_provider"
_PENDING_TTL_SEC = 900


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


def _ordered_cli_names(project_root: Path) -> list[str]:
    avail = DeploymentDetector.detect_available(str(project_root))
    names = [str(c.get("name") or "") for c in avail if c.get("name")]
    order = list(DeploymentDetector.PRIORITY)
    out: list[str] = []
    for k in order:
        if k in names:
            out.append(k)
    for k in names:
        if k not in out:
            out.append(k)
    return out


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

    parsed = parse_deploy_intent(raw)

    if parsed and parsed.get("provider"):
        _clear_pending(db, uid)

    if parsed is None:
        if not pending:
            return None
        choice = parse_deploy_choice_reply(raw, list(pending.get("options") or []))
        if not choice:
            opts = list(pending.get("options") or [])
            lines = [
                "**Pick a cloud for this deploy**",
                "",
                "Reply with the **number** or say **`deploy to <tool>`**.",
                "",
            ]
            for i, name in enumerate(opts, 1):
                lines.append(f"{i}. **{name}**")
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
    workspace = _deploy_workspace_root()
    root = find_project_root(Path(workspace))
    preview = str(parsed.get("deploy_type") or "deploy") == "deploy_preview"
    explicit = str(parsed.get("provider") or "").strip() or None

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
            lines = [
                "**Which cloud should deploy this folder?**",
                "",
                f"_Deploy root:_ `{root}`",
                "",
            ]
            for i, name in enumerate(opts, 1):
                lines.append(f"{i}. **{name}**")
            lines.append("")
            lines.append("Reply with the **number** or **`deploy to <vercel|railway|…>`**.")
            lines.append("_Your choice is remembered for the next plain `deploy`._")
            return {
                "mode": "chat",
                "text": gateway_finalize_chat_reply("\n".join(lines), source="deploy_choice", user_text=raw),
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
        lines += (
            "\n**Install a CLI:** `npm i -g vercel` · `brew install railway` · "
            "see https://fly.io/docs/hobbyists/install-flyctl/\n"
        )
    return {
        "mode": "chat",
        "text": gateway_finalize_chat_reply(lines.strip(), source="generic_deploy_fail", user_text=raw),
        "intent": "deployment_failed",
        "deployment": result,
    }


__all__ = ["parse_deploy_choice_reply", "try_gateway_deploy_turn"]
