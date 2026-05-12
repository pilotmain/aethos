# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
User custom agents: persistence, safety defaults, and LLM reply path.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.audit_log import AuditLog
from app.models.user_agent import UserAgent
from app.repositories.telegram_repo import TelegramRepository
from app.services import user_api_keys
from app.services.custom_agent_templates import (
    REGULATED_TEMPLATE_AGENT_KEYS,
    _generic,
    template_for_phrase,
)
from app.services.llm_action_types import CHAT_RESPONSE
from app.services.llm_key_resolution import ResolvedLLM, resolve_llm_for_user
from app.services.llm_usage_context import push_llm_action
from app.services.runtime_capabilities import log_guardrail_block
from app.services.user_capabilities import get_telegram_role_for_app_user, is_trusted_or_owner

logger = logging.getLogger(__name__)


def _audit_custom_agent_event(
    db: Session,
    *,
    event_type: str,
    actor: str,
    message: str,
    user_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append audit row without importing audit_service (avoids gateway↔audit cycles)."""
    md = dict(metadata or {})
    try:
        from app.services.channel_gateway.origin_context import get_channel_origin

        co = get_channel_origin()
        if isinstance(co, dict):
            for ck in ("channel", "channel_user_id"):
                v = co.get(ck)
                if v is not None:
                    md[ck] = str(v)[:256]
    except Exception:  # noqa: BLE001 — never block agent flows on audit enrichment
        pass
    row = AuditLog(
        user_id=(user_id or None),
        job_id=None,
        event_type=(event_type or "")[:64],
        actor=(actor or "")[:32],
        message=(message or "")[:4000],
        metadata_json=md,
    )
    db.add(row)
    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.warning("custom agent audit commit failed: %s", exc)

from app.services.mention_control import CATALOG_KEY_TO_INTERNAL, MENTION_ALIASES  # noqa: WPS433

DANGER_TOOL_KEYWORDS: frozenset[str] = frozenset(
    {
        "dev execution",
        "code execution",
        "file mutation",
        "write file",
        "deploy",
        "deployment",
        "browser preview",
        "playwright",
        "ssh",
        "credentials",
        "api key in agent",
    }
)

NEXA_BASE = (
    "AethOS safety: reply helpfully. You may receive governed local file/folder access through AethOS's "
    "approval flow — do not claim you cannot access the user's filesystem; say approval may be needed. "
    "Do not request or assume unsupervised access to the user's device, dev jobs, repos, or credentials. "
    "This turn is text-only unless AethOS injects host tool results. "
)

# @boss — avoid stale refusals (“no sessions_spawn”) when runtime tools exist; appended manifest lists truth.
BOSS_LLM_BASE = (
    "AethOS safety: reply helpfully. You may receive governed local file/folder access through AethOS's "
    "approval flow. When the user names agents and a goal (bounded supervised work), **sessions_spawn** is "
    "invoked by deterministic chat routes — do not refuse delegation as “I cannot assign sub-agents”; "
    "confirm results only when the reply already shows spawn_group_id / assignment ids from AethOS. "
    "Do **not** ask “Should I proceed?”, “please confirm”, or “awaiting backend confirmation” when the message "
    "is already a complete bounded supervised mission — deterministic routing executes first; summarize **real** "
    "IDs returned by AethOS only. "
    "You **cannot** create unrestricted autonomous agents or recurring unsupervised loops without approval. "
    "Do not request credentials or unsupervised host access."
)

# @boss — NEXA_WORKSPACE_MODE=developer: orchestrator-forward; pair with runtime capability truth block.
BOSS_LLM_DEVELOPER = (
    "You are a **governed orchestrator** with access to runtime tools when this deployment enables them. "
    "Execute **valid bounded missions** automatically: deterministic routes may call **sessions_spawn** and "
    "**background_heartbeat** before you respond — do **not** refuse with “I cannot use sessions_spawn”, "
    "“I am read-only”, “this is blocked”, or “tools are unavailable” when the **Runtime capability truth** "
    "block shows those capabilities as enabled. "
    "Never claim the system is **permanently locked** or tools are **gone forever**; if a flag is off, say what "
    "is off and how to enable it (for example **`NEXA_AGENT_TOOLS_ENABLED`**). "
    "Block only substantive risks: **unbounded** recurring autonomy without oversight, **recursive** unsupervised "
    "agent loops, and **unrestricted** system or credential access. "
    "Do **not** ask for redundant confirmation when the user already issued a complete bounded supervised mission — "
    "summarize **real** spawn and assignment IDs from AethOS. "
    "Do not request credentials or unsupervised host access."
)

# Prepended in developer workspace mode for all custom agents (short anti-false-refusal hint).
DEVELOPER_WORKSPACE_HINT = (
    "Workspace mode: **developer**. Do not use blanket phrases like “I am read-only”, “I cannot use "
    "**sessions_spawn**”, or “the platform is permanently locked” when the capability truth below shows those "
    "features are enabled."
)

BASE_OPERATOR_TEMPLATE = (
    "You are an AethOS **Base Operator**.\n\n"
    "You operate inside a developer-mode workspace when **`NEXA_WORKSPACE_MODE=developer`**.\n\n"
    "You may use only tools that appear in the runtime tool manifest and capability truth blocks.\n\n"
    "If a valid bounded runtime tool request applies, execution goes through the **AethOS backend** — do **not** "
    "simulate tool calls or invent **`spawn_…`** ids.\n\n"
    "When approvals are disabled for local testing (**`NEXA_APPROVALS_ENABLED=false`** with developer mode), do "
    "not ask for redundant confirmation on turns AethOS already audited — still refuse unbounded autonomy and "
    "unsafe requests.\n\n"
    "Do **not** claim a tool ran unless the backend returned success.\n\n"
    "Do **not** claim you are read-only when runtime tools are enabled."
)

BOSS_TOOLS_DISABLED_LINE = (
    "Governed runtime tools (**sessions_spawn**, **background_heartbeat**) are **disabled** on this "
    "workspace (`NEXA_AGENT_TOOLS_ENABLED=false`). Planning and coordination guidance only."
)


def normalize_agent_key(name: str) -> str:
    t = (name or "").lower().strip()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c if c.isalnum() or c in " -_" else "" for c in t)
    t = t.replace(" ", "_").replace("-", "_")
    t = re.sub(r"_+", "_", t).strip("_")
    t = t[:64] or "assistant"
    return t


def display_agent_handle_label(stored_key: str) -> str:
    """Canonical chat/UI label: underscores → hyphens (DB often stores underscores)."""
    s = (stored_key or "").strip()
    return s.replace("_", "-")[:64] if s else ""


def display_agent_handle(stored_key: str) -> str:
    """User-facing ``@handle`` with hyphens."""
    lab = display_agent_handle_label(stored_key)
    return f"@{lab}" if lab else "@assistant"


def validate_dangerous_capability_request(user_message: str) -> str | None:
    m = (user_message or "").lower()
    for k in DANGER_TOOL_KEYWORDS:
        if k in m:
            log_guardrail_block(
                "dangerous_capability_keyword",
                detail=str(k)[:120],
            )
            return (
                "I can add the **persona** as an LLM-only custom agent, but it will **not** have dev, "
                "ops, browser preview, deployment, or file mutation access. If you need real tools, that "
                "requires owner review and a separate flow later."
            )
    return None


def _all_reserved_mention_keys() -> set[str]:
    s: set[str] = set()
    for d in (CATALOG_KEY_TO_INTERNAL, MENTION_ALIASES):
        for a, b in d.items():
            s.add(str(a).lower().strip())
            s.add(str(b).lower().strip())
    s.update(
        {
            "aethos",
            "nexa",
            "general",
            "g",
            "system",
            "overwhelm_reset",
            "developer",
            "personal_admin",
        }
    )
    s.discard("")
    return s


_PRODUCT_BUILTIN_HANDLES: frozenset[str] = frozenset(
    {"dev", "ops", "strategy", "research", "marketing", "qa", "reset", "admin"}
)


def is_builtin_product_handle(key: str) -> bool:
    k = (key or "").lower().strip()
    return k in _PRODUCT_BUILTIN_HANDLES


def _is_reserved_key(key: str) -> bool:
    k = (key or "").lower().strip()
    if not k:
        return True
    if k in _PRODUCT_BUILTIN_HANDLES:
        return True
    return k in _all_reserved_mention_keys()


def user_has_any_byok(db: Session, app_user_id: str) -> bool:
    link = TelegramRepository().get_by_app_user(db, app_user_id)
    if not link or not link.telegram_user_id:
        return False
    for m in user_api_keys.list_user_providers(db, int(link.telegram_user_id)):
        if m.has_key:
            return True
    return False


def _no_llm_for_custom_agents_message(resolved: ResolvedLLM) -> str:
    if resolved.reason and "USE_REAL_LLM" in (resolved.reason or ""):
        return (
            "Custom agents need an LLM, but **USE_REAL_LLM** is off on this server.\n\n"
            "Set `USE_REAL_LLM=true` and configure API keys, then restart the API."
        ).strip()
    return (
        "Custom agents need an LLM key.\n\n"
        "I could not find a **user** key or a **system** provider key for this account.\n\n"
        "**Options:**\n"
        "• Add your own key: `/key set openai …` or `/key set anthropic …` (Telegram)\n"
        "• Or configure **ANTHROPIC_API_KEY** / **OPENAI_API_KEY** on the server (.env)\n"
        "• Restart the API after changing environment variables\n\n"
        "Use `/key status` to see what this server resolves for you."
    ).strip()


def can_user_create_custom_agents(db: Session, app_user_id: str) -> tuple[bool, str | None]:
    rrole = (get_telegram_role_for_app_user(db, app_user_id) or "guest") or "guest"
    if is_trusted_or_owner(rrole):
        return (True, None)
    resolved = resolve_llm_for_user(db, app_user_id)
    if resolved.available:
        return (True, None)
    return (False, _no_llm_for_custom_agents_message(resolved))


def get_custom_agent(
    db: Session, user_id: str, agent_key: str
) -> UserAgent | None:
    k = normalize_agent_key(agent_key)
    if not k:
        return None
    u = (user_id or "").strip()[:64] or "unknown"
    k_alt = k.replace("_", "-")
    r = (
        db.scalars(
            select(UserAgent)
            .where(
                UserAgent.owner_user_id == u,
                or_(UserAgent.agent_key == k, UserAgent.agent_key == k_alt),
            )
            .limit(1)
        )
    ).first()
    return r


def list_active_custom_agents(db: Session, user_id: str) -> list[UserAgent]:
    u = (user_id or "").strip()[:64] or "unknown"
    return list(
        db.scalars(
            select(UserAgent)
            .where(
                UserAgent.owner_user_id == u,
                UserAgent.is_active.is_(True),  # type: ignore[union-attr]
            )
            .order_by(UserAgent.agent_key)  # type: ignore[union-attr, arg-type]
        )
        .all()  # type: ignore[call-overload]
    )


REGULATED_AGENT_SYSTEM_PREFIX = (
    "Governance: this profile is marked **regulated-domain**. You are not a licensed professional. "
    "Support research, drafting assistance, summarization, and education only. Require human review "
    "for decisions that bind the user. Never guarantee outcomes.\n\n"
)


def _materialize(
    display_label: str,
) -> tuple[str, str, str, str, str, list[str]]:
    tpl = template_for_phrase(display_label)
    slvl = "standard"
    if tpl is not None:
        key, disp, desc, pr = tpl
        if key in REGULATED_TEMPLATE_AGENT_KEYS:
            slvl = "regulated"
        if _is_reserved_key(key):
            key = normalize_agent_key(f"{key}_custom")
    else:
        nk = normalize_agent_key(re.sub(r"[^a-z0-9\s\-_]+", " ", display_label, flags=re.I) or "my_agent")
        if _is_reserved_key(nk):
            nk = f"my_{nk}"[:64]
        key, disp, desc, pr = _generic(display_label.strip()[:200] or "Assistant", nk)
        dl = (display_label or "").lower()
        if any(
            w in dl
            for w in (
                "attorney",
                "lawyer",
                "legal counsel",
                "doctor",
                "physician",
                "diagnosis",
                "tax preparer",
                "cpa ",
                "financial fiduciary",
            )
        ):
            slvl = "regulated"
    return key, disp, desc, pr, slvl, []


def create_custom_agent(
    db: Session,
    user_id: str,
    display_label: str,
    *,
    system_prompt: str | None = None,
    description: str | None = None,
    force_agent_key: str | None = None,
) -> UserAgent:
    key, disp, desc, pr, slvl, tools = _materialize(display_label)
    if (force_agent_key or "").strip():
        fk = normalize_agent_key(force_agent_key or "")
        if not _is_reserved_key(fk):
            key = fk[:64]
    if _is_reserved_key(key):
        key = f"{key}_1"[:64] if not key.endswith("1") else f"{key}_2"[:64]
    ex = get_custom_agent(db, user_id, key)
    sp = (system_prompt or pr).strip() or pr
    ds = (description or desc).strip() or desc
    if (force_agent_key or "").strip() and (description or "").strip():
        disp = (description or display_label)[:200].strip() or disp
    u = (user_id or "").strip()[:64] or "unknown"
    if ex:
        ex.display_name = str(disp)[:200]
        ex.description = str(ds)[:20_000]
        ex.system_prompt = str(sp)[:50_000]
        ex.allowed_tools_json = "[]"
        ex.safety_level = str(slvl)[:32]
        ex.is_active = True
        ex.set_allowed_tools([])
        db.add(ex)
        db.commit()
        db.refresh(ex)
        return ex
    row = UserAgent(
        owner_user_id=u,
        agent_key=str(key)[:64],
        display_name=str(disp)[:200],
        description=ds,
        system_prompt=sp,
        allowed_tools_json="[]",
        safety_level=slvl,
        is_active=True,
    )
    row.set_allowed_tools(tools)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_many_custom_agents(
    db: Session, user_id: str, display_labels: Sequence[str]
) -> list[UserAgent]:
    out: list[UserAgent] = []
    for lab in display_labels:
        t = (lab or "").strip()
        if t:
            out.append(create_custom_agent(db, user_id, t))
    return out


def delete_custom_agent(db: Session, user_id: str, agent_key: str) -> bool:
    k = (agent_key or "").lower().strip()[:64]
    r = get_custom_agent(db, user_id, k)
    if not r:
        return False
    r.is_active = False
    db.add(r)
    db.commit()
    return True


def list_custom_agents(db: Session, user_id: str) -> list[UserAgent]:
    u = (user_id or "").strip()[:64] or "unknown"
    return list(
        db.scalars(
            select(UserAgent)
            .where(UserAgent.owner_user_id == u)
            .order_by(UserAgent.agent_key)  # type: ignore[union-attr, arg-type]
        )
        .all()  # type: ignore[call-overload]
    )


def run_custom_user_agent(
    db: Session,
    app_user_id: str,
    agent: UserAgent,
    user_message: str,
    *,
    source: str = "telegram",
) -> str:
    s = get_settings()
    m = (user_message or "").strip()[:12_000]
    if not m:
        return f"**{agent.display_name}** — add a message after the @mention so I can help."
    if not s.use_real_llm or (not s.anthropic_api_key and not s.openai_api_key) and not user_has_any_byok(
        db, app_user_id
    ):
        return (
            f"**{agent.display_name}** needs a configured LLM on the server, or a BYOK key in `/keys`, "
            "so I can reply."
        )
    nk = normalize_agent_key(agent.agent_key)
    from app.services.runtime_capabilities import (
        format_runtime_truth_prompt_block,
        is_developer_workspace_mode,
    )

    sys_chunks: list[str] = []
    if is_developer_workspace_mode():
        sys_chunks.append(DEVELOPER_WORKSPACE_HINT.strip())
        sys_chunks.append(BASE_OPERATOR_TEMPLATE.strip())

    if nk == "boss":
        if s.nexa_agent_tools_enabled:
            boss_base = (
                BOSS_LLM_DEVELOPER.strip()
                if is_developer_workspace_mode()
                else BOSS_LLM_BASE.strip()
            )
            sys_chunks.append(boss_base)
            if (agent.safety_level or "").strip().lower() == "regulated":
                sys_chunks.append(REGULATED_AGENT_SYSTEM_PREFIX.strip())
            sys_chunks.append(agent.system_prompt.strip())
            from app.services.agent_runtime.tool_registry import format_tools_prompt_block

            sys_chunks.append(format_tools_prompt_block())
            sys_chunks.append(format_runtime_truth_prompt_block())
        else:
            sys_chunks.extend([NEXA_BASE.strip(), BOSS_TOOLS_DISABLED_LINE])
            if (agent.safety_level or "").strip().lower() == "regulated":
                sys_chunks.append(REGULATED_AGENT_SYSTEM_PREFIX.strip())
            sys_chunks.append(agent.system_prompt.strip())
            sys_chunks.append(format_runtime_truth_prompt_block())
    else:
        sys_chunks.append(NEXA_BASE.strip())
        if (agent.safety_level or "").strip().lower() == "regulated":
            sys_chunks.append(REGULATED_AGENT_SYSTEM_PREFIX.strip())
        sys_chunks.append(agent.system_prompt.strip())
    sysm = "\n\n".join(x for x in sys_chunks if x)[:32_000]
    try:
        from app.services.safe_llm_gateway import safe_llm_text_call

        with push_llm_action(
            action_type=CHAT_RESPONSE,
            agent_key=f"user:{agent.agent_key}"[:64],
        ):
            body = (safe_llm_text_call(system_prompt=sysm, user_request=m) or "").strip()[:9000]
    except Exception as e:  # noqa: BLE001
        logger.warning("custom agent llm: %s", e)
        return f"**{agent.display_name}** had trouble generating a reply. Try again in a moment."
    if not body:
        return f"**{agent.display_name}** — (empty reply) try rephrasing."
    from app.services.markdown_postprocess import clean_agent_markdown_output

    body = clean_agent_markdown_output(body)
    from app.services.response_sanitizer import (
        sanitize_developer_mode_stale_copy,
        sanitize_fake_sessions_spawn_reply,
    )

    if nk == "boss":
        body = sanitize_fake_sessions_spawn_reply(body, user_text=m)
    body = sanitize_developer_mode_stale_copy(body)
    _audit_custom_agent_event(
        db,
        event_type="custom_agent.used",
        actor="aethos",
        message=f"Custom agent @{agent.agent_key} reply",
        user_id=app_user_id,
        metadata={"handle": agent.agent_key, "source": source[:32]},
    )
    return f"**{agent.display_name}** —\n\n{body}"


def format_unknown_with_custom(base_message: str, db: Session, app_user_id: str) -> str:
    act = [a for a in list_active_custom_agents(db, app_user_id) if a]
    if not act:
        return f"{base_message}\n\nAsk in chat: **Create me a custom agent** to add your own (LLM-only, no builder UI)."
    tail = "\n".join(f"· `@{a.agent_key}`" for a in act[:20])
    return f"{base_message}\n\nYour custom agents (AethOS LLM-only):\n{tail}"


def format_creation_reply(agents: Sequence[UserAgent], *, danger_line: str | None) -> str:
    lines = [f"Created {len(agents)} custom **AethOS** agent(s) (LLM-only, no dev/ops tools by default):"]
    for a in agents:
        lines.append(
            f"· `@{a.agent_key}` — {a.description[:180] + ('…' if len(a.description) > 180 else '') if a.description else 'See /agent describe'}"
        )
    lines += [
        "",
        "Try:",
        f"· `@{agents[0].agent_key} help with …`" if agents else "· (none)",
    ]
    if danger_line:
        lines += ["", danger_line]
    return "\n".join(lines)[:10_000]


def try_custom_agent_capability_guidance(
    db: Session, app_user_id: str, user_text: str
) -> str | None:
    """Deterministic reply when user asks whether custom agents exist or asks for regulated roles."""
    from app.services.custom_agent_intent import (
        is_custom_agent_capability_inquiry,
        is_regulated_professional_misuse_request,
    )

    if is_regulated_professional_misuse_request(user_text):
        return (
            "I can’t configure an agent to deliver **final** licensed professional advice or fully replace "
            "a lawyer, doctor, or CPA.\n\n"
            "What AethOS **does** support is a **regulated-domain assistant profile**: research, summaries, "
            "drafting support, issue spotting, and **explicit human-review** requirements. Final decisions "
            "belong with qualified professionals.\n\n"
            "Say **Create me a custom agent:** … with the role you want, or ask for a legal-style research "
            "assistant by name."
        ).strip()

    if not is_custom_agent_capability_inquiry(user_text):
        return None

    ok, err = can_user_create_custom_agents(db, app_user_id)
    parts = [
        "**Yes — AethOS supports custom agent profiles.** The built-in specialists (Developer, QA, Ops, Strategy, "
        "Marketing, Research) are **starter defaults**; you can add your own agents with role, instructions, "
        "tools (when enabled), knowledge hooks, and governance boundaries.",
        "",
        "For a **legal-style** assistant: it is **not** a licensed attorney. It can support legal research, "
        "document review, summarization, drafting assistance, clause comparison, and issue spotting — with "
            "sensitive materials staying permissioned and auditable through AethOS’s normal approval flows.",
        "",
        "Examples:\n"
        "• Create me a custom agent: **senior attorney — legal research & contract review**\n"
        "• Create an agent called **@attorney** for document review",
    ]
    if not ok:
        parts.extend(["", err or "Custom agents aren’t available on this account right now."])
    else:
        parts.extend(
            [
                "",
                "Some advanced routing features may still be evolving on your workspace, but you can define "
                "the profile and @mention handle here under AethOS’s governance layer.",
            ]
        )
    return "\n".join(parts).strip()


def try_conversational_create_custom_agents(
    db: Session, app_user_id: str, user_text: str
) -> str | None:
    from app.services.custom_agent_intent import (
        is_custom_agent_creation_intent,
        parse_agent_title_lines_from_message,
    )

    t = (user_text or "").strip()
    if not is_custom_agent_creation_intent(t):
        return None
    ok, err = can_user_create_custom_agents(db, app_user_id)
    if not ok:
        return err or "I can’t add custom agents on this account right now."
    lines = parse_agent_title_lines_from_message(t)
    if not lines:
        return (
            "I can add **custom agents** in AethOS (LLM-only; no dev/ops tools by default). "
            "List them, for example:\n"
            "Create me a few agents:\n"
            "1. financial advisor\n"
            "2. fitness coach"
        )
    dline = validate_dangerous_capability_request(t)
    ags = create_many_custom_agents(db, app_user_id, lines)
    if not ags:
        return "I couldn’t create any agents from that. Try a shorter name per line."
    return format_creation_reply(ags, danger_line=dline)


def _build_product_instruction_block(spec: Any) -> str:
    from app.services.custom_agent_parser import ParsedCustomAgent

    assert isinstance(spec, ParsedCustomAgent)
    lines = [
        f"You are @{spec.handle}, a custom AethOS agent.",
        "",
        "Role:",
        spec.role,
        "",
        "Capabilities:",
    ]
    for s in spec.skills:
        lines.append(f"- {s}")
    if not spec.skills:
        lines.append("- (User-defined scope; follow the role above.)")
    lines += ["", "Guardrails:"]
    for g in spec.guardrails:
        lines.append(f"- {g}")
    if not spec.guardrails:
        lines.append("- AethOS LLM-only — no autonomous host, dev, or file tools unless enabled.")
    lines += [
        "",
        "Output style: concise, structured, risk-aware; state uncertainty when needed.",
    ]
    if spec.safety_level == "regulated":
        lines[:0] = [REGULATED_AGENT_SYSTEM_PREFIX.rstrip(), ""]
    return "\n".join(lines)[:50_000]


def create_custom_agent_from_prompt(
    db: Session,
    *,
    user_id: str,
    prompt: str,
    channel_origin: dict | None = None,
) -> str:
    """
    Parse natural-language create request, validate, persist UserAgent, audit, return user-facing text.
    """
    from app.services.custom_agent_intent import is_regulated_professional_misuse_request
    from app.services.custom_agent_parser import (
        extract_explicit_agent_creation_handles,
        parse_custom_agent_from_prompt,
    )

    _ = channel_origin
    raw = (prompt or "").strip()

    if is_regulated_professional_misuse_request(raw):
        _audit_custom_agent_event(
            db,
            event_type="custom_agent.rejected_regulated_misuse",
            actor="aethos",
            message="Rejected regulated-professional misuse framing for custom agent create.",
            user_id=user_id,
            metadata={"prompt_preview": raw[:500]},
        )
        return (
            "I can’t create an agent framed as **replacing a licensed professional** or giving **binding final advice**.\n\n"
            "I **can** create `@legal-reviewer` as a **legal research and contract review assistant** — summaries, "
            "risk notes, draft questions, and human-review checkpoints.\n\n"
            'Try: **Create me a custom agent called @legal-reviewer.** It should review contracts, summarize risks, '
            "draft questions, and require human review before final decisions."
        )

    explicit_handles = extract_explicit_agent_creation_handles(raw)
    if explicit_handles:
        created: list[Any] = []
        skip_msgs: list[str] = []
        for hk in explicit_handles:
            key = normalize_agent_key(hk)
            if is_builtin_product_handle(key) or _is_reserved_key(key):
                skip_msgs.append(f"`@{key}` is reserved — skipped.")
                continue
            sp = (
                f"You are @{key}, an AethOS custom agent created from an explicit team list.\n\n"
                "Follow the user's instructions; stay within scope."
            )
            agent = create_custom_agent(
                db,
                user_id,
                display_label=key.replace("-", " ").title(),
                description=f"Explicit swarm agent `{key}`."[:2000],
                system_prompt=sp,
                force_agent_key=key,
            )
            agent.safety_level = "standard"
            db.add(agent)
            db.commit()
            db.refresh(agent)
            created.append(agent)
            _audit_custom_agent_event(
                db,
                event_type="custom_agent.created",
                actor="aethos",
                message=f"Created custom agent @{agent.agent_key} (explicit list)",
                user_id=user_id,
                metadata={"handle": agent.agent_key, "source": "explicit_list"},
            )
        if not created:
            return "\n".join(skip_msgs) if skip_msgs else (
                "No valid handles in **create these agents** list (reserved or invalid)."
            )
        dline = validate_dangerous_capability_request(raw)
        tail = "\n\n" + "\n".join(skip_msgs) if skip_msgs else ""
        return format_creation_reply(created, danger_line=dline) + tail

    spec = parse_custom_agent_from_prompt(raw)
    if spec is None:
        return (
            "Say **Create me a custom agent called @your-handle** and what it should do (comma-separated is fine)."
        )

    key = normalize_agent_key(spec.handle)
    if is_builtin_product_handle(key) or _is_reserved_key(key):
        return (
            f"`@{key}` is reserved for a built-in or system role. "
            f"Pick another handle, e.g. `@{key}-helper` or `@{key}-assistant`."
        )

    danger = validate_dangerous_capability_request(raw)

    sys_prompt = _build_product_instruction_block(spec)
    agent = create_custom_agent(
        db,
        user_id,
        spec.display_name,
        description=spec.description[:20_000],
        system_prompt=sys_prompt,
        force_agent_key=key,
    )
    agent.safety_level = spec.safety_level[:32]
    db.add(agent)
    db.commit()
    db.refresh(agent)

    _audit_custom_agent_event(
        db,
        event_type="custom_agent.created",
        actor="aethos",
        message=f"Created custom agent @{agent.agent_key}",
        user_id=user_id,
        metadata={"handle": agent.agent_key, "safety_level": spec.safety_level},
    )

    return format_custom_agent_product_created(spec, danger_line=danger)


def format_custom_agent_product_created(
    spec: Any,
    *,
    danger_line: str | None,
) -> str:
    from app.services.custom_agent_parser import ParsedCustomAgent

    assert isinstance(spec, ParsedCustomAgent)
    lines = [
        f"Created custom agent @{spec.handle}.",
        "",
        "Role:",
        spec.role,
        "",
        "Skills:",
    ]
    if spec.skills:
        for s in spec.skills:
            lines.append(f"- {s}")
    else:
        lines.append("- (Scope follows your instructions when you @mention this agent.)")
    lines += ["", "Guardrails:"]
    if spec.guardrails:
        for g in spec.guardrails:
            lines.append(f"- {g}")
    else:
        lines.append("- Human review for consequential decisions; LLM-only — no automatic host actions.")
    lines += [
        "",
        "Use it by saying:",
        f"@{spec.handle} review this contract",
    ]
    if spec.safety_level == "regulated":
        lines += [
            "",
            "Note: This is a regulated-domain assistant. It supports research, drafting, and review; "
            "final decisions should be reviewed by a qualified professional.",
        ]
    if danger_line:
        lines += ["", danger_line]
    return "\n".join(lines)


def format_custom_agent_describe_reply(db: Session, user_id: str, handle: str) -> str:
    k = normalize_agent_key((handle or "").strip().lstrip("@"))
    row = get_custom_agent(db, user_id, k)
    dh = display_agent_handle(k)
    if not row:
        return (
            f"I don’t see {dh} yet. You can create it by saying:\n"
            "**Create me a custom agent called " + dh + "** …"
        )
    st = "enabled" if row.is_active else "disabled"
    sl = (row.safety_level or "standard").strip()
    drow = display_agent_handle(row.agent_key)
    return (
        f"**{drow}** ({st})\n"
        f"· Display name: {row.display_name}\n"
        f"· Safety level: {sl}\n"
        f"· Description: {(row.description or '—')[:900]}\n\n"
        f"Instructions begin:\n{(row.system_prompt or '')[:1200]}"
        + ("…" if len(row.system_prompt or "") > 1200 else "")
    )


def format_custom_agents_list_reply(db: Session, user_id: str) -> str:
    act = list_active_custom_agents(db, user_id)
    if not act:
        return (
            "You don’t have any **custom agents** yet.\n\n"
            "Create your first, for example:\n"
            "**Create me a custom agent called @legal-reviewer** — contract review and risk notes."
        )
    lines = ["Your custom agents:", ""]
    for a in act[:40]:
        badge = (getattr(a, "safety_level", None) or "standard")[:32]
        ah = display_agent_handle(a.agent_key)
        lines.append(f"- `{ah}` — *{badge}* — {(a.description or a.display_name)[:140]}")
    return "\n".join(lines)


def resolve_disable_enable_delete(
    db: Session,
    user_id: str,
    handle: str,
    *,
    disable: bool | None = None,
    delete: bool = False,
    append_enable_resend_hint: bool = False,
) -> str:
    k = normalize_agent_key((handle or "").strip().lstrip("@"))
    row = get_custom_agent(db, user_id, k)
    if not row:
        dh = display_agent_handle(k)
        return (
            f"I don’t see {dh} yet. Create it with:\n"
            "**Create me a custom agent called "
            + dh
            + "** …"
        )
    dh = display_agent_handle(row.agent_key)
    if delete:
        delete_custom_agent(db, user_id, k)
        _audit_custom_agent_event(
            db,
            event_type="custom_agent.deleted",
            actor="aethos",
            message=f"Deleted {dh}",
            user_id=user_id,
            metadata={"handle": k},
        )
        return f"Deleted {dh}."
    if disable is True:
        row.is_active = False
        db.add(row)
        db.commit()
        _audit_custom_agent_event(
            db,
            event_type="custom_agent.disabled",
            actor="aethos",
            message=f"Disabled {dh}",
            user_id=user_id,
            metadata={"handle": k},
        )
        return f"Disabled {dh}. It won’t respond to @mentions until you enable it again."
    if disable is False:
        row.is_active = True
        db.add(row)
        db.commit()
        _audit_custom_agent_event(
            db,
            event_type="custom_agent.enabled",
            actor="aethos",
            message=f"Enabled {dh}",
            user_id=user_id,
            metadata={"handle": k},
        )
        base = f"Enabled {dh}."
        if append_enable_resend_hint:
            base += "\n\nPlease resend the task you want it to run."
        return base
    return "No action."


def resolve_update_custom_agent(db: Session, user_id: str, text: str) -> str:
    m = re.match(r"(?is)^update\s+@([\w-]{1,64})\s+(.+)$", (text or "").strip())
    if not m:
        return "Try: **update @my-agent** to also summarize termination clauses"
    k_raw, instr = m.group(1), (m.group(2) or "").strip()
    k = normalize_agent_key(k_raw)
    row = get_custom_agent(db, user_id, k)
    if not row:
        return f"I don’t see `@{k}` to update."
    add = f"\n\n[User update]: {instr[:8000]}"
    row.system_prompt = (row.system_prompt or "") + add
    row.description = ((row.description or "") + " " + instr[:500])[:20_000]
    db.add(row)
    db.commit()
    _audit_custom_agent_event(
        db,
        event_type="custom_agent.updated",
        actor="aethos",
        message=f"Updated @{k}",
        user_id=user_id,
        metadata={"handle": k},
    )
    return f"Updated `@{k}`.\n\nAdded instructions:\n{instr[:2000]}"
