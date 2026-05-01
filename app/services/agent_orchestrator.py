from __future__ import annotations

import logging
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.services.agent_router import route_agent
from app.services.memory_aware_routing import apply_memory_aware_route_adjustment

logger = logging.getLogger(__name__)


def _public_url_read_response(
    db: Session,
    app_user_id: str,
    text: str,
    *,
    conversation_snapshot: dict | None = None,
    is_research: bool = False,
) -> str | None:
    """
    If URLs are in `text`, fetch and optionally synthesize. Returns None when there
    is nothing to do (no URLs) so the caller can fall back.
    """
    from app.core.config import get_settings
    from app.services.browser_preview import is_static_fetch_likely_too_little
    from app.services.user_capabilities import get_telegram_role_for_app_user, is_owner_role
    from app.services.web_access import (
        PublicPageSummary,
        format_page_summary_for_prompt,
        summarize_public_page,
    )
    from app.services.web_research_intent import (
        app_user_allows_internal_fetch,
        extract_urls_from_text,
    )

    t = (text or "").strip()
    urls = extract_urls_from_text(t, max_urls=2)
    if not urls:
        return None
    try:
        from app.services.audit_service import audit
        from app.services.nexa_safety_policy import policy_audit_metadata

        audit(
            db,
            event_type="safety.orchestrator.boundary",
            actor="nexa",
            user_id=app_user_id,
            message="public_url_read",
            metadata={
                **policy_audit_metadata(),
                "instruction_source": "web_page",
                "boundary": "orchestrator_public_url_read",
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("orchestrator boundary audit skipped: %s", exc)
    s = get_settings()
    if not s.nexa_web_access_enabled:
        msg = "Public web read is off on this server (NEXA_WEB_ACCESS_ENABLED=false)."
        if is_research:
            return f"🔎 **Research** (Nexa)\n\n{msg}"
        return f"**Nexa** — {msg}"
    allow_in = app_user_allows_internal_fetch(db, app_user_id)
    tool_parts: list[str] = []
    summaries: list[PublicPageSummary] = []
    for u in urls:
        sp = summarize_public_page(
            u, allow_internal=allow_in, db=db, owner_user_id=app_user_id
        )
        summaries.append(sp)
        tool_parts.append(format_page_summary_for_prompt(sp))
    ctx = "\n\n---\n\n".join(tool_parts)[:8_000] if tool_parts else ""

    if s.use_real_llm and (s.anthropic_api_key or s.openai_api_key) and ctx:
        try:
            from app.services.llm_usage_context import push_llm_action
            from app.services.safe_llm_gateway import safe_llm_text_call

            prologue = (
                "You are Nexa. The user asked about one or more public web pages. "
                "Nexa already fetched each URL with a read-only HTTP(s) request (not a real browser, no logins, no form submission in this build). "
                "Summarize products, services, or other concrete facts you can see in the excerpt. Always cite the Source: URL. "
                "If the tool output says the request failed, explain using: I could not access the public page because … (copy the reason) and keep the paste-text hint lines. "
                "Do not say you cannot browse or that you cannot open public URLs — the tool already ran. "
                "If the data says the request failed, timed out, or was blocked, do not invent what is on the site. "
            )
            with push_llm_action(
                action_type="public_url_summary", agent_key="research" if is_research else "nexa"
            ):
                out = safe_llm_text_call(
                    system_prompt=prologue,
                    user_request=f"User: {t}\n\n{ctx}\n",
                )
            body = (out or "").strip()[:9000]
        except Exception as exc:  # noqa: BLE001
            logger.exception("public url read llm: %s", exc)
            body = ctx[:9000] if ctx else "The fetch did not return usable text; turn on the LLM for a structured answer."
    elif ctx and not s.use_real_llm:
        body = (
            "I read the public page (read-only fetch). For a full summary, enable `USE_REAL_LLM` and an API key. "
            "Tool output (excerpts; cite Source lines below):\n\n" + ctx[:9000]
        )
    else:
        body = (ctx or "").strip()
    body = (body or "").strip()

    if summaries and s.nexa_web_access_enabled and body:
        has_thin = any(
            ssum.ok
            and is_static_fetch_likely_too_little(ssum.text_excerpt)
            and not (ssum.user_message or "").strip()
            for ssum in summaries
        )
        if has_thin and not re.search(
            r"(?i)browser preview", body
        ):
            rrole = get_telegram_role_for_app_user(db, app_user_id)
            if is_owner_role(rrole) and s.nexa_browser_preview_enabled:
                body = (
                    body
                    + "\n\n_The static page has limited text; it may be JavaScript-rendered. "
                    "As owner, you can try: `@research browser preview <url>` (Playwright on the host — see doctor)._"
                )
            elif is_owner_role(rrole) and not s.nexa_browser_preview_enabled:
                body = (
                    body
                    + "\n\n_The static page has limited text. Browser preview (owner) is off — "
                    "set `NEXA_BROWSER_PREVIEW_ENABLED=true` and install Playwright to render in a headless browser._"
                )
            elif not is_owner_role(rrole):
                body = (
                    body
                    + "\n\n_The static page has limited text; the site may need JavaScript that this fetch does not run._"
                )

    if is_research and body:
        return (
            "🔎 **Research** (Nexa)\n\n"
            f"I used Nexa’s public read-only page fetch. Here is what to take from the visible text:\n\n{body[:9000]}"
        )
    if is_research and not body:
        return f"🔎 **Research** (Nexa)\n\nI could not get any text from the URL(s) you shared."
    if not body:
        return None
    return (
        f"**Nexa** — I used a public read-only fetch. Here is what the page(s) returned:\n\n{body[:9000]}"
    )


_WEB_SEARCH_OFF_MSG = (
    "Live web search is not enabled on this host: set `NEXA_WEB_SEARCH_ENABLED=true`, "
    "`NEXA_WEB_SEARCH_PROVIDER` (brave, tavily, or serpapi), and `NEXA_WEB_SEARCH_API_KEY`, "
    "then restart the API and bot. You can still paste a public `https://` link — I can read the page text read-only."
)


def _synthesize_from_search(user_question: str, sr, *, is_research: bool) -> str:
    from app.core.config import get_settings
    from app.schemas.web_ui import WebResponseSourceItem
    from app.services.safe_llm_gateway import safe_llm_text_call
    from app.services.web_search import format_search_results_for_prompt
    from app.services.web_turn_extras import set_web_turn_extra

    s = get_settings()
    ctx = format_search_results_for_prompt(sr)
    if not sr.results:
        prov = getattr(sr, "provider", "unknown")
        msg = (
            f"Web search ({prov}) did not return useful hits for this phrasing. "
            "You can try a more specific question, or paste a direct public `https://` link and ask me to check that page."
        )
        if is_research:
            return f"🔎 **Research** (Nexa)\n\n{msg}"
        return f"**Nexa** — {msg}"
    prologue = (
        "You are Nexa. The user asked a question that was answered using a read-only web search tool. "
        "Base factual claims on the search snippets and Source URLs only. Cite the Source: lines. "
        "If snippets are off-topic or too thin, say that clearly. Do not claim you fully read entire pages; "
        "Nexa only has titles and short snippets (Phase 2)."
    )
    body: str
    if s.use_real_llm and (s.anthropic_api_key or s.openai_api_key):
        try:
            from app.services.llm_usage_context import push_llm_action

            with push_llm_action(
                action_type="web_search_summary", agent_key="research" if is_research else "nexa"
            ):
                body = (
                    safe_llm_text_call(
                        system_prompt=prologue,
                        user_request=f"User: {user_question}\n\n{ctx}\n",
                    )
                    or ""
                ).strip()[:9000]
        except Exception as exc:  # noqa: BLE001
            logger.exception("web search llm: %s", exc)
            body = ctx[:8000]
    else:
        body = f"From the tool (read-only; cite every Source: URL the user can open):\n\n{ctx[:8000]}"
    sources = [
        WebResponseSourceItem(url=r.url, title=(r.title or None)[:400] if r.title else None)
        for r in sr.results
    ]
    set_web_turn_extra("web_search", sources)
    pshow = sr.provider
    if is_research:
        return (
            "🔎 **Research** (Nexa)\n\n"
            f"I used a web search ({pshow}) for up-to-date public information. Here is a concise read:\n\n{body}\n"
        )[:10_000]
    return (
        f"**Nexa** — I used a web search ({pshow}) to answer. Here is a concise read:\n\n{body}\n"
    )[:10_000]


def _run_search_or_none(
    _db: Session,  # noqa: ARG001 — reserved for future policy
    _app_user_id: str,
    user_text: str,
    *,
    is_research: bool,
) -> str | None:
    """
    If user wants web search and the stack is on, return a full reply. If search is
    'off' but intent matches, return the 'not enabled' one-liner. If no web-search
    intent, return None to continue routing.
    """
    from app.core.config import get_settings
    from app.services.web_research_intent import should_use_web_search
    from app.services.web_search import (
        MissingWebSearchKey,
        WebSearchDisabled,
        extract_user_search_query_for_intent,
        search_web,
    )

    t = (user_text or "").strip()
    if not should_use_web_search(t):
        return None
    s = get_settings()
    if not s.nexa_web_search_enabled:
        if is_research:
            return f"🔎 **Research** (Nexa)\n\n{_WEB_SEARCH_OFF_MSG}"
        return _WEB_SEARCH_OFF_MSG
    q = extract_user_search_query_for_intent(t, is_research_mention=is_research)
    if not (q or "").strip():
        return None
    try:
        sr = search_web((q or t).strip(), requester_role=None)
    except WebSearchDisabled:
        if is_research:
            return f"🔎 **Research** (Nexa)\n\n{_WEB_SEARCH_OFF_MSG}"
        return _WEB_SEARCH_OFF_MSG
    except MissingWebSearchKey:
        m = (
            "Web search is enabled, but the provider or API key is not configured. "
            "The host should set `NEXA_WEB_SEARCH_PROVIDER` to brave, tavily, or serpapi and set `NEXA_WEB_SEARCH_API_KEY` (see doctor)."
        )
        if is_research:
            return f"🔎 **Research** (Nexa)\n\n{m}"
        return f"**Nexa** — {m}"
    except Exception as e:  # noqa: BLE001
        # Do not block the whole turn on provider/network failure — fall through to normal LLM routing.
        logger.warning(
            "web search failed (%s): %s",
            type(e).__name__,
            str(e)[:300],
            exc_info=True,
        )
        return None
    return _synthesize_from_search((q or t)[:1_200], sr, is_research=is_research)


def _build_marketing_public_url_blocks(
    db: Session,
    app_user_id: str,
    user_text: str,
) -> tuple[str, list]:
    """
    Read-only public URL excerpts for the Marketing agent (for prompt injection). Returns
    (formatted block for the LLM, list of PublicPageSummary for optional thin-page note).
    """
    from app.core.config import get_settings
    from app.services.web_access import format_page_summary_for_prompt, summarize_public_page
    from app.services.web_research_intent import (
        app_user_allows_internal_fetch,
        extract_urls_from_text,
    )

    urls = extract_urls_from_text((user_text or "").strip(), max_urls=2)
    if not urls:
        return "", []
    s = get_settings()
    if not s.nexa_web_access_enabled:
        joined = ", ".join(urls)
        return (
            f"Public web read is not enabled on this host (NEXA_WEB_ACCESS_ENABLED=false). "
            f"The user referenced: {joined}. You cannot have fetched them; do not list products as if you did. "
            f"Use the user-facing phrasing: {joined} is not available to read on this host (or the user can paste the text).",
            [],
        )
    allow_in = app_user_allows_internal_fetch(db, app_user_id)
    tool_parts: list[str] = []
    summaries = []
    for u in urls:
        sp = summarize_public_page(
            u, allow_internal=allow_in, db=db, owner_user_id=app_user_id
        )
        summaries.append(sp)
        tool_parts.append(format_page_summary_for_prompt(sp))
    block = "\n\n---\n\n".join(tool_parts)[:8_000] if tool_parts else ""
    if not (block or "").strip():
        return "No public page text was returned (empty tool output).", summaries
    return _MARKETING_PAGE_TOOL_INTRO + block, summaries


_MARKETING_PAGE_TOOL_INTRO = (
    "Public page read (tool, read-only HTTP; not a real browser, no logins, no form submission in this build):\n"
)


def _append_marketing_thin_page_note(
    db: Session,
    app_user_id: str,
    summaries: list,
    body: str,
) -> str:
    """If static fetch is thin, append the same owner/non-owner note as the research URL path."""
    b = (body or "").strip()
    if not b or not summaries:
        return body
    from app.core.config import get_settings
    from app.services.browser_preview import is_static_fetch_likely_too_little
    from app.services.user_capabilities import get_telegram_role_for_app_user, is_owner_role

    s = get_settings()
    if not s.nexa_web_access_enabled:
        return body
    has_thin = any(
        ssum.ok
        and is_static_fetch_likely_too_little((ssum.text_excerpt or ""))
        and not (ssum.user_message or "").strip()
        for ssum in summaries
    )
    if not has_thin or re.search(r"(?i)browser preview", b):
        return body
    rrole = get_telegram_role_for_app_user(db, app_user_id)
    if is_owner_role(rrole) and s.nexa_browser_preview_enabled:
        return (
            b
            + "\n\n_The static page has limited text; it may be JavaScript-rendered. "
            "As owner, you can try: `@research browser preview <url>` (Playwright on the host — see doctor)._"
        )
    if is_owner_role(rrole) and not s.nexa_browser_preview_enabled:
        return (
            b
            + "\n\n_The static page has limited text. Browser preview (owner) is off — "
            "set `NEXA_BROWSER_PREVIEW_ENABLED=true` and install Playwright to render in a headless browser._"
        )
    if not is_owner_role(rrole):
        return (
            b
            + "\n\n_The static page has limited text; the site may need JavaScript that this fetch does not run._"
        )
    return b


def _marketing_any_fetched_page_is_thin_for_search(summaries: list) -> bool:
    """If static fetch is minimal and search is on, add supplemental web search for marketing."""
    from app.services.browser_preview import is_static_fetch_likely_too_little

    for ssum in summaries or []:
        if not getattr(ssum, "ok", True):
            continue
        if (getattr(ssum, "user_message", None) or "").strip():
            continue
        if is_static_fetch_likely_too_little((ssum.text_excerpt or "")):
            return True
    return False


def _web_items_from_page_summaries(summaries: list) -> list:
    from app.schemas.web_ui import WebResponseSourceItem

    out: list[WebResponseSourceItem] = []
    for s in summaries or []:
        u = (getattr(s, "source_url", None) or "").strip()
        if not u:
            continue
        t = (getattr(s, "title", None) or None) if hasattr(s, "title") else None
        out.append(
            WebResponseSourceItem(
                url=u[:800],
                title=(t or None)[:400] if t else None,
            )
        )
    return out


def _dedupe_web_source_items(
    items: list,
) -> list:
    from app.schemas.web_ui import WebResponseSourceItem

    seen: set[str] = set()
    out: list[WebResponseSourceItem] = []
    for it in items or []:
        if not isinstance(it, WebResponseSourceItem):
            continue
        u = (it.url or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(it)
    return out


def _set_marketing_response_metadata(
    public_summaries: list,
    search_source_items: list,
) -> None:
    from app.schemas.web_ui import WebResponseSourceItem
    from app.services.web_turn_extras import set_web_turn_extra

    pub = _web_items_from_page_summaries(public_summaries)
    sk = [x for x in (search_source_items or []) if isinstance(x, WebResponseSourceItem)]
    merged = _dedupe_web_source_items(pub + sk)
    if not merged:
        return
    if pub and sk:
        tline = "Tool: Public web read + Web search"
    elif pub:
        tline = "Tool: Public web read"
    else:
        tline = "Tool: Web search"
    set_web_turn_extra("marketing_web_analysis", merged, tool_line=tline)


def _run_marketing_search_block_for_prompt(
    db: Session,  # noqa: ARG001 — future policy
    _app_user_id: str,
    user_text: str,
    *,
    resolved_urls: list[str],
    use_site_constrained_query: bool = False,
) -> tuple[str | None, list]:
    """
    Read-only search for marketing. Caller decides whether to run (per supplemental-intent
    and thin-page rules). Returns (prompt block or policy/error string, search result items).
    """
    from app.core.config import get_settings
    from app.schemas.web_ui import WebResponseSourceItem
    from app.services.web_research_intent import build_marketing_search_query_against_url
    from app.services.web_search import (
        MissingWebSearchKey,
        WebSearchDisabled,
        extract_user_search_query_for_intent,
        format_search_results_for_prompt,
        search_web,
    )

    t = (user_text or "").strip()
    rlist = [u for u in (resolved_urls or []) if (u or "").strip()]
    s = get_settings()
    if not s.nexa_web_search_enabled:
        return (
            (
                "Web search (tool) is not enabled on this host. "
                "In your reply, say live web search is not turned on for this install (do not claim you personally cannot search). "
                f"User requested: {t[:800]!r}."
            ),
            [],
        )
    if use_site_constrained_query and rlist:
        q = build_marketing_search_query_against_url(t, rlist[0])
    else:
        q = (extract_user_search_query_for_intent(t, is_research_mention=False) or t or "").strip()[:1_200]
    if not (q or "").strip():
        return None, []
    try:
        sr = search_web((q or t).strip(), requester_role=None)
    except WebSearchDisabled:
        return (
            "Web search (tool) is not enabled. Say that search is not configured, briefly (no secrets).",
            [],
        )
    except MissingWebSearchKey:
        return (
            "Web search is misconfigured (missing or invalid API key for the selected provider). "
            "Mention the host can fix provider keys; do not dump secrets.",
            [],
        )
    except Exception as e:  # noqa: BLE001
        logger.info("marketing web search failed: %s", type(e).__name__)
        return "Web search could not complete. Offer the user a page paste or a retry. Do not invent sources.", []
    ctx = format_search_results_for_prompt(sr)
    if not sr.results:
        return f"Web search returned no results for this phrasing. Tool output: {ctx[:2_000]}", []
    sources: list[WebResponseSourceItem] = [
        WebResponseSourceItem(url=r.url, title=(r.title or None)[:400] if r.title else None)
        for r in sr.results
    ]
    block = f"Web search (tool, read-only snippets) provider={sr.provider!s}:\n{ctx[:6_000]}"
    return block, sources


_MARKETING_SYS_WITH_TOOLS = (
    "You are the Marketing agent for Nexa, a personal AI command center. "
    "You may receive a **Public page read (tool, read-only)** section and/or a **Web search (tool, read-only)** section. "
    "If Source: lines appear, those tools already ran — do not say you cannot browse, perform live web searches, or open public https links. "
    "If the tool text shows a failed fetch, timeout, or block, say once: I could not access the page because {reason} — you can paste the text here and I can still help. Do not invent page contents. "
    "If a section says public web is off on the host, say that briefly; if search failed or is off, say the host’s search is not available — never claim a personal inability. "
    "Ground product and company names in the tool text only. Do not feign certainty when evidence is thin. "
    "When the evidence is solid, be direct: give clear recommendations; when the evidence is weak, qualify briefly in one short clause, then still give your best single recommendation. "
    "\n"
    "When tool output is thin or does not name clear products, start the body with a single line: "
    "I found limited product detail from the public page/search results. "
    "Then still provide: Insight (what is missing or unclear, what could improve), a provisional **Positioning** read (with light hedging in-line), and what content would help marketing. "
    "\n"
    "When you have enough evidence, skip that limited-detail line. "
    "\n"
    "Use this **exact Markdown section structure** (## headings, bullets) so every answer is scannable and expert-level, not a generic list:\n"
    "\n"
    "## What I found\n"
    "- Products or services you can name from the tools, each with a one-line summary if the text supports it.\n"
    "\n"
    "## Insight\n"
    "- What is interesting, unusual, or strong (from the evidence).\n"
    "- What is missing, weak, or unclear in how the business presents itself (call out messaging gaps frankly).\n"
    "- Tight bullets — this section is the ‘why it matters’ layer; avoid repeating **What I found** verbatim.\n"
    "\n"
    "## Positioning\n"
    "- Lead with decisive framing when tools support it: e.g. **This is best positioned as…** or **The strongest positioning angle is…**; name the audience. "
    "If evidence is thin, still give one best recommendation, and prefix with a short honest caveat (e.g. ‘Based on limited public copy…’), not permanent hedging in every sentence.\n"
    "- One line: who it is for (or ‘likely for …’ with a one-clause uncertainty note only if needed).\n"
    "\n"
    "## Marketing angles\n"
    "- 3–5 bullets. Each angle must be **concrete and actionable**: name channel(s) and audience where it fits "
    "(e.g. ‘LinkedIn + founders in ops-heavy indie SaaS’), not generic ‘focus on benefits’ phrasing. "
    "Tie each angle to something from **What I found** or **Insight**.\n"
    "\n"
    "## Suggested copy\n"
    "- **Homepage headline** — one line.\n"
    "- **Subheadline** — one short line.\n"
    "- **CTA** — one short call-to-action line (button-style or under-the-fold; max ~12 words).\n"
    "- **LinkedIn post hook** — one line that could open a post (not a whole post).\n"
    "\n"
    "## Sources\n"
    "- List every Source: URL from the tool output (or say none if tools failed completely).\n"
    "\n"
    "Do not open dev job flows or name private code repos. This path does not create development tasks."
)

_MARKETING_SYS_OFFLINE = (
    "You are the Marketing agent for Nexa (a personal AI command center). "
    "Help with positioning, taglines, landing copy, user personas, or a launch post. "
    "Be concrete and concise. Do not create development tasks or mention code repos."
)

# Appended to offline marketing when LLM is available (complements _MARKETING_SYS_WITH_TOOLS full structure)
def _marketing_offline_structured_suffix() -> str:
    from app.services.structured_response_style import structured_style_guidance_for

    return "\n\n" + structured_style_guidance_for("marketing", None)


def handle_ops_agent_request(
    _db: Session, _app_user_id: str, text: str
) -> str:
    from app.services.worker_heartbeat import build_dev_health_report

    body = (build_dev_health_report() or "").strip() or "No local worker heartbeat file yet. On the host, run the dev executor or use `/dev health`."
    return (
        f"⚙️ **Ops Agent** (Nexa) — local / worker check (read-only, best-effort):\n\n"
        f"{body[:8000]}\n\n_Your message: {text[:500]}_"
    )


def handle_nexa_request(
    db: Session,
    app_user_id: str,
    text: str,
    *,
    memory_service,
    orchestrator,
    conversation_snapshot: dict | None = None,
    routing_agent_key: str | None = None,
) -> str:
    from app.core.config import get_settings
    from app.services.behavior_engine import (
        apply_tone,
        build_context,
        build_response,
        no_tasks_response,
    )
    from app.services.intent_classifier import get_intent
    from app.services.routing.authority import should_suppress_public_web_pipeline
    from app.services.web_research_intent import should_use_public_url_read

    intent = get_intent(text, conversation_snapshot=conversation_snapshot)
    ctx = build_context(db, app_user_id, memory_service, orchestrator)
    _s = get_settings()
    suppress_web = should_suppress_public_web_pipeline(text)
    if (
        not suppress_web
        and _s.nexa_web_access_enabled
        and should_use_public_url_read(text)
    ):
        purl = _public_url_read_response(
            db,
            app_user_id,
            text,
            conversation_snapshot=conversation_snapshot,
            is_research=False,
        )
        if purl is not None:
            return apply_tone(purl, ctx.memory)
    if not suppress_web:
        wsearch = _run_search_or_none(db, app_user_id, text, is_research=False)
        if wsearch is not None:
            return apply_tone(wsearch, ctx.memory)
    if intent == "brain_dump":
        result = orchestrator.generate_plan_from_text(
            db, app_user_id, text, input_source="telegram", intent="brain_dump"
        )
        if result.get("needs_more_context"):
            return apply_tone(no_tasks_response(), ctx.memory)
        orchestrator.users.mark_user_onboarded(db, app_user_id)
        ctx2 = build_context(db, app_user_id, memory_service, orchestrator)
        body = build_response(
            text,
            intent,
            ctx2,
            plan_result=result,
            db=db,
            app_user_id=app_user_id,
            conversation_snapshot=conversation_snapshot,
            routing_agent_key=routing_agent_key,
        )
        return apply_tone(body, ctx2.memory)
    body = build_response(
        text,
        intent,
        ctx,
        plan_result=None,
        db=db,
        app_user_id=app_user_id,
        conversation_snapshot=conversation_snapshot,
        routing_agent_key=routing_agent_key,
    )
    return apply_tone(body, ctx.memory)


def _qa_mvp_for_job(
    db: Session,
    app_user_id: str,
    t: str,
    *,
    get_job,
) -> str | None:
    """If text references a job id, return a QA block; else None to fall back to general QA line."""
    jid: int | None = None
    m = re.search(r"(?i)review\s+job\s*#?(\d+)", t)
    if m:
        jid = int(m.group(1))
    if jid is None:
        m2 = re.search(r"(?i)job\s*#?(\d+)", t)
        if m2:
            jid = int(m2.group(1))
    if jid is None and re.match(r"^\#?(\d+)\s*$", t.strip()):
        jid = int(re.match(r"^\#?(\d+)\s*$", t.strip()).group(1))
    if jid is None:
        return None
    job = get_job(db, app_user_id, jid)
    if not job:
        return f"🧪 QA Agent — I couldn’t find job #{jid} for your account."
    st = (getattr(job, "status", None) or "—")[:120]
    ts = (getattr(job, "tests_status", None) or "").strip()
    wtype = (getattr(job, "worker_type", None) or "")
    ad = (getattr(job, "artifact_dir", None) or "").strip() or (
        (getattr(job, "failure_artifact_dir", None) or "").strip()
    )
    has_test_log = False
    test_snip = ""
    if ad:
        base = Path(ad)
        for name in ("tests_stdout.log", "tests_stderr.log"):
            p = base / name
            if p.is_file() and p.stat().st_size > 0:
                has_test_log = True
                test_snip = p.read_text(encoding="utf-8", errors="replace")[-2000:]
                break
    interpret = "Review the test logs on the host and whether status matches your expectations before merge."
    if ts == "failed" or (st or "").lower() == "failed":
        interpret = "This job is in a failed or failing-tests posture — inspect logs and diffs before retrying or approving."
    lines = [
        f"🧪 **QA Agent** (Nexa) — job #{job.id}",
        f"- Status: {st}",
    ]
    if wtype:
        lines.append(f"- Worker: {wtype}")
    if ts:
        lines.append(f"- Test status: {ts}")
    else:
        lines.append("- Test status: (not set in DB)")
    if has_test_log and test_snip:
        lines.append("\n**Recent test log (tail):**\n" + test_snip[:2500])
    else:
        lines.append("\nI don’t see test output for that job yet (or artifacts are on another host).")
    lines.append(
        f"\n**Commands:** `/job {job.id}` — `/job {job.id} tests` — `/job {job.id} logs`"
    )
    lines.append(f"\n_Interpretation: {interpret}_")
    return "\n".join(lines)[:10_000]


def handle_qa_agent_request(
    db: Session,
    app_user_id: str,
    text: str,
) -> str:
    from app.services.agent_job_service import AgentJobService

    js = AgentJobService()
    t = (text or "").strip()
    block = _qa_mvp_for_job(db, app_user_id, t, get_job=js.get_job)
    if block:
        return block
    return (
        "🧪 **QA Agent** (Nexa) — I can help with test plans, failures, and regressions. "
        "Try: `@qa review job 4` or describe a failure. Use `@dev` to queue a code fix (same dev job path).\n\n"
        f"Your request: {text[:1200]}"
    )


def handle_marketing_agent_request(
    db: Session,
    app_user_id: str,
    text: str,
    *,
    conversation_snapshot: dict | None = None,  # noqa: ARG001 — API parity with research
) -> str:
    t = (text or "").strip()
    t_user = re.sub(r"^\s*@marketing\s+", "", t, flags=re.I).strip() or t
    from app.core.config import get_settings
    from app.services.routing.authority import should_suppress_public_web_pipeline
    from app.services.web_research_intent import (
        extract_urls_from_text,
        marketing_message_mentions_web_research_intent_with_url,
        should_use_marketing_supplemental_web_search,
    )

    s = get_settings()
    if should_suppress_public_web_pipeline(t):
        from app.services.general_answer_service import answer_general_question

        body = answer_general_question(
            f"Marketing request (public web tools suppressed — orchestration/spawn context was detected in "
            f"the same message): {t_user}",
            conversation_snapshot=conversation_snapshot,
            research_mode=False,
        )
        return f"📣 **Marketing Agent** (Nexa)\n\n{body}"[:10_000]

    resolved = extract_urls_from_text(t, max_urls=2)
    has_url = bool(resolved)
    url_block, page_summaries = _build_marketing_public_url_blocks(db, app_user_id, t)
    mkt_web_signal = marketing_message_mentions_web_research_intent_with_url(t) if has_url else False
    explicit_search = should_use_marketing_supplemental_web_search(t)
    thin_page = (
        bool(resolved)
        and bool(page_summaries)
        and s.nexa_web_access_enabled
        and _marketing_any_fetched_page_is_thin_for_search(page_summaries)
    )
    use_site_query = (explicit_search and has_url) or (bool(thin_page) and has_url)
    want_search = explicit_search or (thin_page and s.nexa_web_search_enabled)
    search_block, search_source_items = (None, [])
    if want_search:
        search_block, search_source_items = _run_marketing_search_block_for_prompt(
            db,
            app_user_id,
            t,
            resolved_urls=resolved,
            use_site_constrained_query=use_site_query,
        )

    use_tool_prompt = (
        has_url
        or mkt_web_signal
        or (search_block is not None)
        or ((url_block or "").strip() and has_url and not s.nexa_web_access_enabled)
    )
    parts: list[str] = [f"User: {t_user[:3_500]}"]
    if (url_block or "").strip():
        parts.append(f"\n---\n{url_block[:7_000]}")
    if (search_block or "").strip():
        parts.append(f"\n---\n{str(search_block)[:6_000]}")
    user_blob = "\n".join(parts).strip()[:9_200]
    if use_tool_prompt:
        sys_prompt = _MARKETING_SYS_WITH_TOOLS
    else:
        sys_prompt = f"{_MARKETING_SYS_OFFLINE}{_marketing_offline_structured_suffix()}"

    def _emit_mkt_meta() -> None:
        if page_summaries or search_source_items:
            _set_marketing_response_metadata(
                list(page_summaries or []), list(search_source_items or [])
            )

    if s.use_real_llm and (s.openai_api_key or s.anthropic_api_key) and t:
        try:
            from app.services.llm_usage_context import push_llm_action
            from app.services.safe_llm_gateway import safe_llm_text_call

            with push_llm_action(
                action_type="marketing_synthesis" if use_tool_prompt else "marketing_chat",
                agent_key="marketing",
            ):
                out = safe_llm_text_call(
                    system_prompt=sys_prompt,
                    user_request=user_blob,
                )
            out = (out or "").strip()
            if not out:
                out = (user_blob[:1_200] or t_user) if use_tool_prompt else t_user
            if has_url and page_summaries:
                out = _append_marketing_thin_page_note(db, app_user_id, page_summaries, out)
            _emit_mkt_meta()
            return f"📣 **Marketing Agent** (Nexa)\n\n{out[:8_200]}"
        except Exception as exc:  # noqa: BLE001
            logger.exception("marketing llm: %s", exc)
            if use_tool_prompt and ((url_block or "").strip() or (search_block or "").strip()):
                tool_fallback = f"{(url_block or '')}\n{search_block or ''}".strip()[:6_000]
                _emit_mkt_meta()
                return (
                    "📣 **Marketing Agent** (Nexa)\n\n"
                    "I had trouble turning the fetch/search into a full draft. "
                    "If you paste any page text, I can still work from it. Tool context (excerpts; cite sources):\n\n"
                    f"{tool_fallback}"
                )
    if not t:
        return "📣 **Marketing Agent** (Nexa) — Send a request (e.g. tagline, launch post, user persona for Nexa)."
    if use_tool_prompt and f"{(url_block or '')}\n{search_block or ''}".strip():
        _emit_mkt_meta()
        tool_blob = f"{(url_block or '')}\n{search_block or ''}".strip()
        return (
            "📣 **Marketing Agent** (Nexa) — I pulled read-only public tool output (or policy notes) below. "
            "For a full strategy draft, enable `USE_REAL_LLM` and a provider key.\n\n" + str(tool_blob)[:7_200]
        )
    return (
        "📣 **Marketing Agent** (Nexa) — Positioning, taglines, landing copy, and launch copy.\n\n"
        f"**Draft (offline):** respond to: {t[:800]!r}\n"
        f"\n(Enable a configured LLM for full drafts. This path never creates dev jobs.)\n"
    )


def handle_strategy_agent_request(
    _db: Session,
    _app_user_id: str,
    text: str,
    conversation_snapshot: dict | None = None,
) -> str:
    t = (text or "").strip()
    topic = ((conversation_snapshot or {}).get("active_topic") or "").strip()
    from app.core.config import get_settings

    s = get_settings()
    if s.use_real_llm and (s.openai_api_key or s.anthropic_api_key) and t:
        try:
            from app.services.safe_llm_gateway import safe_llm_text_call

            extra = f"\n\nActive topic (if useful): {topic[:600]}" if topic else ""
            from app.services.structured_response_style import structured_style_guidance_for

            strat = (
                "You are the Strategy agent for Nexa, a personal AI command center. "
                "Answer with: (1) a clear recommendation, (2) 2–4 short bullets on tradeoffs, (3) one next step. "
                "Be concise. Do not name other products."
            )
            out = safe_llm_text_call(
                system_prompt=f"{strat}\n\n{structured_style_guidance_for('strategy', None)}",
                user_request=t[:4000] + extra,
            )
            return f"🧭 **Strategy Agent** (Nexa)\n\n{out[:4000]}"
        except Exception as exc:  # noqa: BLE001
            logger.exception("strategy llm: %s", exc)
    head = f"**Context topic:** {topic}\n\n" if topic else ""
    return (
        f"🧭 **Strategy Agent** (Nexa)\n\n{head}"
        f"**Question:** {t[:600]!r}\n"
        f"- **Recommendation:** Pick one bet for the next 1–2 weeks; measure one outcome.\n"
        f"- **Tradeoffs:** time vs. scope, B2B depth vs. B2C reach, build vs. partner.\n"
        f"- **Next step:** List two constraints, then choose the smaller experiment.\n"
    )


def handle_cto_agent_request(
    _db: Session, _app_user_id: str, text: str
) -> str:
    return (
        "🏗️ Architecture / CTO Agent (Nexa) — Checklist: SLO/scale, data path, security boundary, "
        f"ops / rollback, vendor risk.\n\nContext: {text[:1200]}"
    )


def handle_research_agent_request(
    db: Session,
    app_user_id: str,
    text: str,
    *,
    conversation_snapshot: dict | None = None,
) -> str:
    t = (text or "").strip()
    if not t or len(t) < 2:
        return (
            "🔎 **Research** (Nexa) — add a topic, e.g. "
            "`@research Ethiopian economy update` or a specific question."
        )
    from app.services.browser_preview import format_preview_for_chat, preview_public_page
    from app.services.general_answer_service import answer_general_question
    from app.services.routing.authority import should_suppress_public_web_pipeline
    from app.services.user_capabilities import get_telegram_role_for_app_user
    from app.services.web_research_intent import (
        extract_url_for_browser_preview,
        extract_urls_from_text,
    )

    suppress_web = should_suppress_public_web_pipeline(t)

    preview_u = extract_url_for_browser_preview(t)
    if preview_u and not suppress_web:
        role = get_telegram_role_for_app_user(db, app_user_id)
        bpr = preview_public_page(preview_u, role)
        block = f"🔎 **Research** (Nexa)\n\n{format_preview_for_chat(bpr)}"
        return block[:10_000]

    if extract_urls_from_text(t, max_urls=1) and not suppress_web:
        block = _public_url_read_response(
            db,
            app_user_id,
            text,
            conversation_snapshot=conversation_snapshot,
            is_research=True,
        )
        if block is not None:
            return block
    if not suppress_web:
        wsearch = _run_search_or_none(db, app_user_id, t, is_research=True)
        if wsearch is not None:
            return wsearch
    body = answer_general_question(
        f"Research-style answer for: {t}. If a live or proprietary source is not available, "
        "say that once, then be useful: structure, and what the user can verify. "
        "Nexa can also fetch a **public** http(s) page when you include a resolvable link.",
        conversation_snapshot=conversation_snapshot,
        research_mode=True,
    )
    return f"🔎 **Research** (Nexa)\n\n{body}"[:10_000]


def handle_personal_admin_request(
    _db: Session, _app_user_id: str, text: str
) -> str:
    return (
        "📋 Personal admin (Nexa) — I can work with your saved memory and plan/tasks. "
        f"Reminders and errands: {text[:1200]}"
    )


def handle_general_agent_request(
    db: Session,
    app_user_id: str,
    text: str,
    *,
    memory_service,
    orchestrator,
    conversation_snapshot: dict | None = None,
    routing_agent_key: str | None = None,
) -> str:
    from app.services.behavior_engine import apply_tone, build_context, build_response, map_intent_to_behavior
    from app.services.intent_classifier import get_intent

    intent = get_intent(text, conversation_snapshot=conversation_snapshot)
    ctx = build_context(db, app_user_id, memory_service, orchestrator)
    body = build_response(
        text,
        intent,
        ctx,
        plan_result=None,
        db=db,
        app_user_id=app_user_id,
        conversation_snapshot=conversation_snapshot,
        routing_agent_key=routing_agent_key,
    )
    b = map_intent_to_behavior(intent, ctx)
    return apply_tone(
        f"{body}\n\n_({b} — no specialist route matched. Try @nexa or @dev.)_",
        ctx.memory,
    )


def handle_ceo_request(
    _db: Session, _app_user_id: str, text: str
) -> str:
    return (
        "👤 CEO / focus agent (Nexa) — I can help decide what matters first; "
        f"share constraints, timeline, and risk.\n\nYour message: {text[:1200]}"
    )


def handle_agent_request(
    db: Session,
    app_user_id: str,
    text: str,
    *,
    memory_service,
    orchestrator,
    context_snapshot: dict | None = None,
) -> str:
    """Heuristic route for natural language (not already handled by @mentions or dev job creation)."""
    from app.services.response_formatter import finalize_user_facing_text

    r = route_agent(text, context_snapshot=context_snapshot)
    r = apply_memory_aware_route_adjustment(r, text, context_snapshot, db)
    key = str(r.get("agent_key") or "general")
    if key in ("nexa", "overwhelm_reset"):
        raw = handle_nexa_request(
            db,
            app_user_id,
            text,
            memory_service=memory_service,
            orchestrator=orchestrator,
            conversation_snapshot=context_snapshot,
            routing_agent_key=str(r.get("agent_key") or "nexa"),
        )
    elif key == "ops":
        raw = handle_ops_agent_request(db, app_user_id, text)
    elif key == "developer":
        raw = (
            "💻 **Dev Agent** — queue work with /improve, a natural “tell Cursor to…”, or `@dev …` "
            "(the Dev Agent is the same autonomous **dev job** path you already use)."
        )
    elif key == "qa":
        raw = handle_qa_agent_request(db, app_user_id, text)
    elif key == "marketing":
        raw = handle_marketing_agent_request(
            db, app_user_id, text, conversation_snapshot=context_snapshot
        )
    elif key == "strategy":
        raw = handle_strategy_agent_request(
            db, app_user_id, text, conversation_snapshot=context_snapshot
        )
    elif key == "ceo":
        raw = handle_ceo_request(db, app_user_id, text)
    elif key == "cto":
        raw = handle_cto_agent_request(db, app_user_id, text)
    elif key == "research":
        raw = handle_research_agent_request(
            db, app_user_id, text, conversation_snapshot=context_snapshot
        )
    elif key == "personal_admin":
        raw = handle_personal_admin_request(db, app_user_id, text)
    else:
        raw = handle_general_agent_request(
            db,
            app_user_id,
            text,
            memory_service=memory_service,
            orchestrator=orchestrator,
            conversation_snapshot=context_snapshot,
            routing_agent_key=str(r.get("agent_key") or "general"),
        )
    up = None
    if memory_service and app_user_id and db is not None:
        try:
            up = memory_service.get_learned_preferences(db, app_user_id)
        except Exception:  # noqa: BLE001
            up = None
    return finalize_user_facing_text(raw, user_preferences=up)


def handle_agent_mention(
    db: Session,
    app_user_id: str,
    agent_key: str,
    text: str,
    *,
    memory_service,
    orchestrator,
    conversation_snapshot: dict | None = None,
) -> str:
    """@mention explicit routing. `developer` is usually handled in the bot to queue a dev job."""
    from app.services.response_formatter import finalize_user_facing_text

    if agent_key in ("nexa", "overwhelm_reset"):
        raw = handle_nexa_request(
            db,
            app_user_id,
            text,
            memory_service=memory_service,
            orchestrator=orchestrator,
            conversation_snapshot=conversation_snapshot,
            routing_agent_key=agent_key,
        )
    elif agent_key == "ops":
        raw = handle_ops_agent_request(db, app_user_id, text)
    elif agent_key == "qa":
        raw = handle_qa_agent_request(db, app_user_id, text)
    elif agent_key == "marketing":
        raw = handle_marketing_agent_request(
            db, app_user_id, text, conversation_snapshot=conversation_snapshot
        )
    elif agent_key == "strategy":
        raw = handle_strategy_agent_request(
            db, app_user_id, text, conversation_snapshot=conversation_snapshot
        )
    elif agent_key == "ceo":
        raw = handle_ceo_request(db, app_user_id, text)
    elif agent_key == "cto":
        raw = handle_cto_agent_request(db, app_user_id, text)
    elif agent_key == "research":
        raw = handle_research_agent_request(
            db, app_user_id, text, conversation_snapshot=conversation_snapshot
        )
    elif agent_key == "personal_admin":
        raw = handle_personal_admin_request(db, app_user_id, text)
    elif agent_key == "developer":
        raw = "💻 Use `@dev` <task> to queue a dev job (same path as /improve or “tell cursor to…”)."
    else:
        raw = handle_general_agent_request(
            db,
            app_user_id,
            text,
            memory_service=memory_service,
            orchestrator=orchestrator,
            conversation_snapshot=None,
            routing_agent_key=agent_key,
        )
    up = None
    if memory_service and app_user_id and db is not None:
        try:
            up = memory_service.get_learned_preferences(db, app_user_id)
        except Exception:  # noqa: BLE001
            up = None
    return finalize_user_facing_text(raw, user_preferences=up)
