"""Map @ops … messages to the same view as dev health and the job queue."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.services.worker_heartbeat import build_dev_health_report


def ops_mention_reply(
    db: Session,
    app_user_id: str,
    m_body: str,
    *,
    list_jobs,
    format_job_row_short,
) -> str | None:
    """
    Return a string for known ops shortcuts, or None to use generic Ops agent handler.
    `list_jobs` and `format_job_row_short` are injected to avoid circular imports.
    """
    t = (m_body or "").strip().lower()
    if not t:
        rep = (build_dev_health_report() or "").strip()
        if not rep:
            return (
                "⚙️ Ops Agent — worker status unknown\n\n"
                "No local heartbeat on file yet. On the host, run the dev executor or use `/dev health`."
            )
        return rep[:12_000]
    if t in ("health", "hb", "worker", "worker status"):
        rep = (build_dev_health_report() or "").strip()
        if not rep:
            return (
                "⚙️ Ops Agent — worker status unknown\n\n"
                "No local heartbeat on file yet. On the host, run the dev executor or use `/dev health`."
            )
        return rep[:12_000]
    if t in ("queue", "dev queue"):
        rows = list_jobs(db, app_user_id, limit=25)
        de = [j for j in rows if (getattr(j, "worker_type", None) or "") == "dev_executor"]
        if not de:
            return "No dev jobs in your recent list."
        block = "Queue (recent dev jobs):\n\n" + "\n\n".join(
            format_job_row_short(x) for x in de[:8]
        )
        return block[:12_000]
    if t in ("jobs", "job", "list"):
        rows = list_jobs(db, app_user_id, limit=5)
        if not rows:
            return "No jobs yet."
        return (
            "Recent jobs:\n\n" + "\n\n".join(format_job_row_short(j) for j in rows)
        )[:12_000]
    if re.match(r"^queue\s*#", t) or t.startswith("job "):
        return None
    if "health" in t and len(t) < 80:
        return ops_mention_reply(
            db, app_user_id, "health", list_jobs=list_jobs, format_job_row_short=format_job_row_short
        )
    return None
