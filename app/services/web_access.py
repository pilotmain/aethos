# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Controlled public HTTP(S) read-only access. No arbitrary browsing — fixed pipeline only.
Never log full URLs with credentials in query; never log request bodies.
"""

from __future__ import annotations

import io
import ipaddress
import logging
import re
import socket
from dataclasses import dataclass, field
from typing import Any
from urllib import robotparser
from urllib.parse import urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Shown to the user when a public fetch fails (read-only; no logins in Phase 1).
_PUBLIC_FETCH_FAIL_ADDENDUM = (
    "\n\nYou can paste the page text here and I can still analyze it."
)


@dataclass
class WebFetchResult:
    url: str
    status_code: int
    final_url: str
    content_type: str
    body_text: str
    truncated: bool
    error: str | None = None
    # Sanitized, non-sensitive — never place secrets here
    log_hint: str = ""


@dataclass
class PublicPageSummary:
    source_url: str
    title: str
    meta_description: str
    text_excerpt: str
    links: list[str] = field(default_factory=list)
    ok: bool = True
    error: str | None = None
    user_message: str = ""  # e.g. blocked, timeout, requires login (heuristic)


def _s(url: str) -> str:
    """Safe URL shape for logging (no userinfo, no query, path truncated)."""
    try:
        p = urlparse(url)
        host = p.hostname or ""
        path = (p.path or "")[:120]
        return f"{p.scheme}://{host}{path}" if p.scheme else host[:200]
    except Exception:  # noqa: BLE001
        return "(unparsed)"


def _truncate_output(s: str, max_len: int | None = None) -> str:
    s = (s or "").replace("\x00", "")
    if max_len is None:
        max_len = get_settings().safe_llm_max_chars
    if len(s) > max_len:
        return s[: max_len - 1].rstrip() + "…"
    return s


def _is_blocked_ssrf_ip(
    a: ipaddress.IPv4Address | ipaddress.IPv6Address, allow_internal: bool
) -> bool:
    if a.is_unspecified or a.is_multicast:
        return True
    if a == ipaddress.IPv4Address("0.0.0.0"):
        return True
    if a == ipaddress.IPv4Address("169.254.169.254"):
        return True
    cgnat = a.version == 4 and a in ipaddress.IPv4Network("100.64.0.0/10", strict=False)
    localish = a.is_private or a.is_loopback or a.is_link_local or cgnat
    if not localish:
        return False
    if not allow_internal:
        return True
    return False


def _all_resolved_ips_safe(
    host: str, allow_internal: bool, port: int
) -> tuple[bool, str | None]:
    if not (host and host.strip()):
        return False, "empty host"
    h = host.strip()
    h = h.strip("[]")
    # Literal IP
    try:
        addr = ipaddress.ip_address(h)
        if _is_blocked_ssrf_ip(addr, allow_internal):
            return False, "host resolves to a blocked address (internal/private)"
        return True, None
    except ValueError:
        pass
    try:
        res = socket.getaddrinfo(
            h, int(port) if port else 443, type=socket.SOCK_STREAM, proto=0
        )
    except OSError as e:  # noqa: BLE001
        return False, f"dns resolution failed: {e!s}"
    seen: set[str] = set()
    for item in res:
        ip = item[4][0]
        if ip in seen:
            continue
        seen.add(ip)
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            return False, "unresolved address form"
        if _is_blocked_ssrf_ip(a, allow_internal):
            return False, "host resolves to a blocked address (internal/private)"
    if not seen:
        return False, "no address records for host"
    return True, None


def validate_public_url_strict(url: str) -> str | None:
    """
    For browser / higher-risk tools: public internet only (no loopback, RFC1918, etc.),
    even for the instance owner. Returns None if ok, else an error string.
    """
    _p, err = _assert_url_safe((url or "").strip(), allow_internal=False)
    return err


def _assert_url_safe(
    url: str, allow_internal: bool, *, for_log: str = "fetch"
) -> tuple[urlparse, str | None]:
    p = urlparse((url or "").strip())
    if p.scheme not in ("http", "https"):
        return p, "only http and https URLs are allowed"
    if not p.netloc or not p.hostname:
        return p, "URL must include a host"
    port = p.port or (443 if p.scheme == "https" else 80)
    if p.username or p.password:
        return p, "URLs with embedded credentials are not allowed (use a vault tool, not a raw URL)"
    safe, err = _all_resolved_ips_safe(p.hostname, allow_internal, port)
    if not safe:
        return p, err
    return p, None


def can_fetch_robots_txt(
    final_url: str, _path: str, allow_internal: bool
) -> tuple[bool, str | None]:
    """
    When practical: if robots disallows the path, skip fetch (stdlib RobotFileParser).
    Returns (allowed, None) or (False, reason). Failure to load robots = allow.
    """
    p0, err = _assert_url_safe((final_url or "").strip(), allow_internal)
    if err or not p0.hostname:
        return True, None
    rurl = f"{p0.scheme}://{p0.netloc}/robots.txt"
    _, re = _assert_url_safe(rurl, allow_internal)
    if re:
        return True, None
    t = get_settings().nexa_web_fetch_timeout_seconds
    try:
        from app.services.safe_http_client import internal_get

        resp = internal_get(rurl, headers=_default_headers(), timeout=float(t), max_redirects=5)
    except (OSError, httpx.RequestError) as e:  # noqa: BLE001
        # DNS / TLS to robots: allow page fetch; best-effort only
        logger.info("web_robots_unavailable: %s", type(e).__name__)
        return True, None
    if int(resp.status_code) >= 400 or not (resp.text or "").strip():
        return True, None
    rp = robotparser.RobotFileParser()
    rp.set_url(rurl)
    try:
        rp.parse(resp.text.splitlines())
    except (TypeError, ValueError) as e:  # noqa: BLE001
        logger.info("web_robots_parse_skip: %s", type(e).__name__)
        return True, None
    ua = get_settings().nexa_web_user_agent
    uastr = (ua or "AethOS/1.0")[:200]
    full = (final_url or "").strip() or p0.geturl()
    if not rp.can_fetch(uastr, full):
        return False, "disallowed by robots.txt for this URL"
    return True, None


def _default_headers() -> dict[str, str]:
    return {
        "User-Agent": get_settings().nexa_web_user_agent.strip() or "AethOS/1.0 (public fetch)",
        "Accept": "text/html, application/xhtml+xml, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }


def _audit_network_external_allowed(
    *,
    db: Any,
    owner_user_id: str,
    hostname: str,
    final_url: str,
    status_code: int,
    workflow_id: str | None,
    run_id: str | None,
    execution_id: str | None,
    job_id: int | None,
) -> None:
    """Trust dashboard: record allowed external GET when egress enforcement was in play."""
    try:
        from app.services.audit_service import audit
        from app.services.trust_audit_constants import NETWORK_EXTERNAL_SEND_ALLOWED

        audit(
            db,
            event_type=NETWORK_EXTERNAL_SEND_ALLOWED,
            actor="web_access",
            user_id=str(owner_user_id).strip()[:64],
            job_id=job_id,
            message=f"GET ok host={hostname} status={status_code}"[:4000],
            metadata={
                "hostname": (hostname or "")[:256],
                "final_url": (final_url or "")[:800],
                "status_code": status_code,
                "method": "GET",
            },
            workflow_id=workflow_id,
            run_id=run_id,
            execution_id=execution_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("trust audit network allowed skipped: %s", exc)


def fetch_url(
    url: str,
    *,
    allow_internal: bool = False,
    respect_robots: bool = True,
    db: Any | None = None,
    owner_user_id: str | None = None,
    workflow_id: str | None = None,
    run_id: str | None = None,
    execution_id: str | None = None,
    job_id: int | None = None,
) -> WebFetchResult:
    """GET url with size limit; validates scheme and SSRF. Does not log secrets."""
    t = (url or "").strip()
    log_hint = _s(t)
    s = get_settings()
    if not s.nexa_web_access_enabled:
        return WebFetchResult(
            t,
            0,
            t,
            "",
            "",
            True,
            error="web access is disabled on this Nexa instance (set NEXA_WEB_ACCESS_ENABLED=true to enable).",
            log_hint=log_hint,
        )
    p, err = _assert_url_safe(t, allow_internal)
    if err:
        logger.info("web_fetch_block reason=%s hint=%s", err, log_hint)
        return WebFetchResult(
            t, 0, t, "", "", True, error=err, log_hint=log_hint
        )
    hn_chk = (p.hostname or "").strip().lower()
    from app.services.enforcement_pipeline import enforce_user_http_get_preflight

    pre_err = enforce_user_http_get_preflight(
        hostname=hn_chk,
        db=db,
        owner_user_id=owner_user_id,
        log_hint=log_hint,
        settings=s,
        workflow_id=workflow_id,
        run_id=run_id,
        execution_id=execution_id,
    )
    if pre_err:
        return WebFetchResult(t, 0, t, "", "", True, error=pre_err, log_hint=log_hint)

    path = (p.path or "/") or "/"
    if respect_robots:
        okr, re = can_fetch_robots_txt(t, path, allow_internal)
        if not okr:
            logger.info("web_fetch blocked by robots hint=%s", log_hint)
            return WebFetchResult(
                t, 0, t, "", "", True, error=re or "robots.txt disallows this path", log_hint=log_hint
            )
    to = s.nexa_web_fetch_timeout_seconds
    max_b = s.nexa_web_max_bytes
    headers = _default_headers()
    try:
        with httpx.Client(
            timeout=httpx.Timeout(to),
            follow_redirects=True,
            max_redirects=s.nexa_web_max_redirects,
            verify=True,
        ) as client:
            with client.stream("GET", t, headers=headers) as resp:
                for hop in list(resp.history) + [resp]:
                    cu = str(hop.url)
                    _, uerr = _assert_url_safe(cu, allow_internal)
                    if uerr:
                        return WebFetchResult(
                            t,
                            0,
                            cu,
                            "",
                            "",
                            True,
                            error=f"redirect blocked: {uerr}",
                            log_hint=_s(cu),
                        )
                st = int(resp.status_code)
                final_url = str(resp.url)
                ct0 = (resp.headers.get("content-type") or "").split(";")[0] or ""
                if 200 <= st < 300:
                    buf = io.BytesIO()
                    total = 0
                    for ch in resp.iter_bytes():
                        total += len(ch)
                        if total > max_b:
                            return WebFetchResult(
                                t,
                                st,
                                final_url,
                                ct0,
                                buf.getvalue()[:max_b].decode("utf-8", errors="replace"),
                                True,
                                error=f"response larger than {max_b} bytes",
                                log_hint=_s(final_url),
                            )
                        buf.write(ch)
                    text = buf.getvalue().decode("utf-8", errors="replace")
                    logger.info("web_fetch ok hint=%s", _s(t))
                    if (
                        getattr(s, "nexa_network_external_send_enforced", False)
                        and db is not None
                        and (owner_user_id or "").strip()
                    ):
                        _audit_network_external_allowed(
                            db=db,
                            owner_user_id=str(owner_user_id).strip(),
                            hostname=hn_chk,
                            final_url=final_url,
                            status_code=st,
                            workflow_id=workflow_id,
                            run_id=run_id,
                            execution_id=execution_id,
                            job_id=job_id,
                        )
                    return WebFetchResult(
                        t, st, final_url, ct0, text, False, log_hint=_s(t)
                    )
                err_body = (resp.read() or b"")[:8_000].decode("utf-8", errors="replace")
                return WebFetchResult(
                    t,
                    st,
                    final_url,
                    ct0,
                    err_body,
                    False,
                    error=f"http {st}",
                    log_hint=_s(final_url),
                )
    except httpx.TimeoutException:
        logger.info("web_fetch timeout hint=%s", log_hint)
        return WebFetchResult(
            t, 0, t, "", "", True, error="request timed out", log_hint=log_hint
        )
    except (OSError, httpx.RequestError) as e:  # noqa: BLE001
        logger.info("web_fetch error hint=%s err=%s", log_hint, type(e).__name__)
        return WebFetchResult(
            t, 0, t, "", "", True, error=f"request failed: {e!s}", log_hint=log_hint
        )


def extract_title(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    t = soup.find("title")
    return _truncate_output((t.get_text() if t else "") or "", 500)


def extract_meta_description(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    m = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if not m and soup.find("head"):
        m = soup.find("head").find(  # type: ignore[union-attr]
            "meta", attrs={"property": re.compile(r"^og:description$", re.I)}
        )
    if not m:
        return ""
    c = m.get("content") or ""
    return _truncate_output(str(c).strip(), 800)


def extract_visible_text(html: str, *, max_chars: int | None = None) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for el in list(soup(["script", "style", "noscript"])):
        el.decompose()
    txt = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in txt.splitlines() if (ln and ln.strip())]
    out = "\n".join(lines)
    return _truncate_output(out, max_len=max_chars or get_settings().safe_llm_max_chars)


def extract_links(html: str, base_url: str) -> list[str]:
    """Absolute http(s) links from href; fragment-only and javascript: skipped."""
    soup = BeautifulSoup(html or "", "html.parser")
    basep = urlparse((base_url or "").strip().split("#")[0])
    out: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href or str(href).lower().startswith(("javascript:", "mailto:")):
            continue
        u = (href or "").strip()
        p = urlparse(u)
        if p.scheme in ("",):
            p2 = p._replace(scheme=basep.scheme, netloc=basep.netloc)
            u = urlunparse(p2)
        elif p.scheme in ("http", "https"):
            u = u.split("#", 1)[0]
        else:
            continue
        if u not in seen and len(u) < 2000:
            seen.add(u)
            out.append(u)
        if len(out) > 200:
            break
    return out


def _login_heuristic(snip: str, status: int) -> str:
    t = (snip or "").lower()
    if status in (401, 403) or re.search(
        r"\b(sign in|log in|login|authentication required|access denied|forbidden)\b",
        t[:4_000],
    ):
        return (
            "I couldn't access the public page because the page may require a login "
            "(this build only fetches public pages, no session)."
        )
    return ""


def summarize_public_page(
    url: str,
    *,
    allow_internal: bool = False,
    db: Any | None = None,
    owner_user_id: str | None = None,
) -> PublicPageSummary:
    """fetch_url + light extraction. No form submission. Safe for the LLM context."""
    t = (url or "").strip()
    fr = fetch_url(
        t,
        allow_internal=allow_internal,
        respect_robots=get_settings().nexa_web_respect_robots,
        db=db,
        owner_user_id=owner_user_id,
    )
    if fr.error is not None:
        msg = (fr.error or "fetch failed")[:1_200]
        body_snip = (fr.body_text or "")[:4_000]
        st = int(fr.status_code or 0)
        auth_hint = _login_heuristic(body_snip, st) or _login_heuristic(msg, st)
        reason = f"{msg} (source: `{_truncate_for_display(t)}`)"
        expl = f"I couldn't access the public page because {reason}." + _PUBLIC_FETCH_FAIL_ADDENDUM
        um = (auth_hint + _PUBLIC_FETCH_FAIL_ADDENDUM) if auth_hint else expl
        return PublicPageSummary(
            source_url=t,
            title="",
            meta_description="",
            text_excerpt=body_snip[:2_000],
            links=[],
            ok=False,
            error=msg,
            user_message=um,
        )
    html = (fr.body_text or "").strip()
    if 200 <= fr.status_code < 300 and not html:
        return PublicPageSummary(
            source_url=t,
            title="",
            meta_description="",
            text_excerpt="",
            links=[],
            ok=True,
            error=None,
            user_message=(
                "I couldn't access the public page because the response had no visible text to read "
                "(it may be non-HTML or empty)."
                + _PUBLIC_FETCH_FAIL_ADDENDUM
            ),
        )
    title = extract_title(html)
    desc = extract_meta_description(html)
    vtext = extract_visible_text(html, max_chars=6_000)
    links = extract_links(html, t or fr.final_url)[:25]
    auth = _login_heuristic(vtext, int(fr.status_code or 0))
    return PublicPageSummary(
        source_url=t,
        title=title,
        meta_description=desc,
        text_excerpt=vtext,
        links=links,
        ok=True,
        error=None,
        user_message=(auth or "").strip(),
    )


def _truncate_for_display(u: str) -> str:
    return (u or "")[:500] + ("" if len(u or "") <= 500 else "…")


def format_page_summary_for_prompt(
    s: PublicPageSummary, *, max_chars: int = 4_000
) -> str:
    """Nexa-internal: inject into the LLM; not shown verbatim to the user on its own."""
    if not s.ok and s.text_excerpt and not s.user_message:
        return f"Fetch failed. Snippet: {_truncate_output(s.text_excerpt, 800)}"
    if not s.ok:
        return s.user_message or (s.error or "fetch failed")
    b = [f"Source: {s.source_url}", f"Title: {s.title or '(none)'}"]
    if s.meta_description:
        b.append(f"Meta: {s.meta_description}")
    if s.text_excerpt:
        b.append("Visible text (excerpt):")
        b.append(_truncate_output(s.text_excerpt, max_len=max_chars))
    if s.links:
        b.append("Notable links:\n" + "\n".join(f"- {x}" for x in s.links[:20]))
    return "\n\n".join(b)[: max_chars + 400]
