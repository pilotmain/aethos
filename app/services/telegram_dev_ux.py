"""User-facing job status and Telegram message helpers (phone-friendly)."""

from __future__ import annotations

STATUS_LABELS: dict[str, str] = {
    "queued": "queued for worker",
    "needs_approval": "needs your approval to start",
    "needs_risk_approval": "high-risk, needs extra approval",
    "approved": "queued for worker",
    "in_progress": "in progress",
    "agent_running": "agent is coding",
    "changes_ready": "changes produced",
    "waiting_approval": "waiting for your approval",
    "changes_requested": "waiting for your revision message",
    "approved_to_commit": "approved, waiting to commit",
    "waiting_for_cursor": "waiting for Cursor on host",
    "ready_for_review": "ready for review",
    "review_approved": "review approved",
    "needs_commit_approval": "needs commit approval",
    "commit_approved": "ready to commit",
    "completed": "completed",
    "failed": "failed",
    "rejected": "rejected",
    "blocked": "blocked by policy",
    "cancelled": "cancelled",
}


def user_friendly_status(status: str | None) -> str:
    s = (status or "unknown").strip() or "unknown"
    return STATUS_LABELS.get(s, s)


def compact_review_for_telegram(review: str, max_chars: int = 3200) -> str:
    r = (review or "").strip()
    if not r or len(r) <= max_chars:
        return r
    head, tail = r[:2200], r[-800:]
    return f"{head}\n\n[…trimmed for Telegram…]\n\n{tail}"


def format_job_row_short(job) -> str:
    """One block per job in a short list (e.g. dev queue, up to 5)."""
    st = (getattr(job, "status", None) or "").strip()
    t = (getattr(job, "title", None) or "—")[:120]
    top = f"#{getattr(job, 'id', '?')} {user_friendly_status(st)} ({st}) {t}"
    sub: list[str] = []
    if (getattr(job, "tests_status", None) or "").strip():
        sub.append(f"  Tests: {getattr(job, 'tests_status', '—')}")
    br = (getattr(job, "branch_name", None) or "").strip()
    if br:
        sub.append(f"  Branch: {br}")
    if st == "failed":
        em = (getattr(job, "error_message", None) or "—").replace("\n", " ")[:220]
        sub.append(f"  Reason: {em}" if em else "  Reason: failed")
    return (top + ("\n" + "\n".join(sub) if sub else "")).strip()


# Dev queue buckets (recent work only — not full history)
_DEV_ACTIVE: frozenset[str] = frozenset(
    {
        "queued",
        "approved",
        "in_progress",
        "agent_running",
        "changes_ready",
        "ready_for_review",
        "commit_approved",
    }
)
_DEV_NEEDS: frozenset[str] = frozenset(
    {
        "needs_approval",
        "needs_risk_approval",
        "waiting_approval",
        "waiting_for_cursor",
        "needs_commit_approval",
        "changes_requested",
        "approved_to_commit",
    }
)


def format_grouped_dev_queue(jobs) -> str:
    """/dev queue — group active, needs you, and recent failures so old failures do not drown the rest."""
    dev = [j for j in (jobs or []) if (getattr(j, "worker_type", None) or "") == "dev_executor"]
    if not dev:
        return "No dev_executor jobs in your recent list."
    act: list = []
    need: list = []
    fail: list = []
    other: list = []
    for j in dev:
        st = (getattr(j, "status", None) or "").strip()
        if st in ("failed", "rejected"):
            fail.append(j)
        elif st in _DEV_ACTIVE:
            act.append(j)
        elif st in _DEV_NEEDS:
            need.append(j)
        else:
            other.append(j)
    n_max = 5
    n_fail = 4

    def _sub(xs: list, title: str, none_msg: str) -> str:
        if not xs:
            return f"**{title}**\n{none_msg}"
        more = f"\n…+{len(xs) - n_max} more (ask in chat for the full list)" if len(xs) > n_max else ""
        body = "\n\n".join(format_job_row_short(x) for x in xs[:n_max])
        return f"**{title}**\n{body}{more}"

    out_lines = [
        "Nexa **dev** queue (recent, grouped; not full history).",
        "",
        _sub(act, "Active (pipeline / worker)", "— (none)"),
        "",
        _sub(need, "Needs you", "— (none)"),
    ]
    if fail:
        extra = f"\n…+{len(fail) - n_fail} more (ask in chat for more)" if len(fail) > n_fail else ""
        fbody = "\n\n".join(format_job_row_short(x) for x in fail[:n_fail]) + extra
        out_lines += [
            "",
            f"**Recent failures (may be old; ask about a job # for time + reason)**\n{fbody}",
        ]
    if other:
        out_lines += ["", _sub(other, "Other statuses", "— (none)")]
    return "\n\n".join(out_lines)[:12_000]


def format_job_detail_telegram(job) -> str:
    """Structured block for dev_executor jobs (Telegram detail view)."""
    w = getattr(job, "worker_type", None) or ""
    st = (getattr(job, "status", None) or "").strip()
    ul = user_friendly_status(st)
    lines = [f"Job #{job.id} — {ul}", f"Status (db): {st}"]

    if w == "dev_executor":
        plj = dict(getattr(job, "payload_json", None) or {})
        rsk = (getattr(job, "risk_level", None) or (plj.get("policy") or {}).get("risk") or "normal")
        lines.append(f"Risk: {rsk}")
        if getattr(job, "tests_status", None):
            lines.append(f"Tests: {getattr(job, 'tests_status', '—')}")
        if (getattr(job, "override_failed_tests", None) or False):
            lines.append("Override: approval allowed despite failed tests (you confirmed on Telegram).")
        if (getattr(job, "branch_name", None) or "").strip():
            lines.append(f"Branch: {job.branch_name}")
        r = (getattr(job, "result", None) or "").strip() or (getattr(job, "error_message", None) or "")
        if r and st not in {"rejected", "blocked"}:
            prev = compact_review_for_telegram(r, 2000)
            if prev:
                lines.append(f"Summary:\n{prev}")
        if st in {"rejected", "failed"} and (getattr(job, "error_message", None) or "").strip() and (job.error_message or "") != (r[: len(job.error_message or "")] if r else ""):
            lines.append(f"Error: {(job.error_message or '')[:1500]}")
        if st == "failed":
            from app.services.dev_orchestrator.retry_advisor import advise_retry

            lines.append("")
            lines.append("Retry advice:")
            lines.append(advise_retry(job))

    jid = getattr(job, "id", "?")
    lines.append("")
    lines.append(
        "Actions: `approve` / `reject` / `show diff` (when job needs approval) — or buttons on the last approval message. "
        f"Ask about job #{jid} for diff or retry, or type `approve despite failed tests` if the job shows failed tests "
        "and you still want to review a commit path."
    )
    return "\n".join(lines)[:12_000]


def format_dev_agent_status_telegram(db, app_user_id: str) -> str:
    """`@dev status` / `/dev status` — default project profile, latest job, worker heartbeat."""
    from app.services.agent_job_service import AgentJobService
    from app.services.dev_orchestrator.project_intelligence import detect_project_profile
    from app.services.project_registry import get_default_project
    from app.services.worker_heartbeat import build_dev_health_report

    js = AgentJobService()
    j = js.get_latest(db, app_user_id)
    lines: list[str] = [
        "**Dev Agent — status (Nexa)**",
        "",
    ]
    if j:
        st = (getattr(j, "status", None) or "unknown").strip()
        tit = (getattr(j, "title", None) or "—")[:120]
        lines.append(f"- Latest job: #{j.id} — {st} — {tit}")
    else:
        lines.append("- Latest job: (none in your recent list)")
    p = get_default_project(db)
    if not p:
        lines.append("- Default project: (none — use `/projects` or `/project add`)")
    else:
        prof = detect_project_profile(p)
        rp_display = (p.repo_path or prof.repo_path or "—") or "—"
        lines.append(f"- Project: **{p.display_name}** (`{p.key}`)")
        lines.append(f"- Repo: `{rp_display}`")
        types = ", ".join(prof.project_types) if prof.project_types else "unknown"
        lines.append(f"- Detected: {types}")
        lines.append(f"- Preferred tool: `{p.preferred_dev_tool or '—'}`")
        lines.append(f"- Mode: `{p.dev_execution_mode or '—'}`")
        wt = "dirty" if prof.dirty else ("clean" if prof.is_git_repo else "n/a (not git)")
        lines.append(f"- Worktree: {wt}")
    hb = (build_dev_health_report() or "").strip()
    lines.append("- Worker / heartbeat:")
    lines.append((hb[:1800] if hb else "(run `/dev health` on the host)")[:2000])
    return "\n".join(lines)[:8000]
