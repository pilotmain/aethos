"""
Owner-only, optional Playwright-based preview of *public* pages (JS-rendered text + screenshot).
Disabled by default. Install: pip install playwright && playwright install chromium
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.services.user_capabilities import is_owner_role
from app.services.web_access import _s, extract_visible_text, validate_public_url_strict
from app.services.worker_heartbeat import RUNTIME_DIR

logger = logging.getLogger(__name__)

PREVIEW_DIR = RUNTIME_DIR / "browser_previews"
PLAYWRIGHT_MISSING_MSG = (
    "Browser preview is not installed on this host. Ask the AethOS host to run: "
    "`pip install playwright` then `playwright install chromium`."
)

_MIN_TEXT_CHARS = 2


@dataclass
class BrowserPreviewResult:
    ok: bool
    final_url: str
    title: str = ""
    text: str = ""
    screenshot_path: str = ""
    error: str | None = None
    # Human-facing; never log secrets
    user_message: str = ""


def _ensure_preview_dir() -> None:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)


def _try_import_sync_playwright() -> Any:
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError:
        return None
    return sync_playwright


def preview_public_page(url: str, requester_role: str) -> BrowserPreviewResult:
    """
    Owner-only, public URLs only, no forms/logins. Screenshot is optional; path returned if saved.
    """
    u = (url or "").strip()
    uerr = validate_public_url_strict(u)
    if uerr:
        logger.info("browser_preview block url: %s", uerr)
        return BrowserPreviewResult(
            False, u, error=uerr, user_message=f"I can't run browser preview: {uerr}"
        )
    if not is_owner_role(requester_role):
        return BrowserPreviewResult(
            False,
            u,
            error="owner-only",
            user_message="Browser preview is only available to the instance owner in this build.",
        )
    s = get_settings()
    if not s.nexa_browser_preview_enabled:
        return BrowserPreviewResult(
            False,
            u,
            error="disabled",
            user_message=(
                "Browser preview is off (set NEXA_BROWSER_PREVIEW_ENABLED=true on the host). "
                "The normal public fetch may still be enough for many pages."
            ),
        )
    spw = _try_import_sync_playwright()
    if spw is None:
        logger.info("browser_preview: playwright not installed")
        return BrowserPreviewResult(
            False,
            u,
            error="playwright-missing",
            user_message=PLAYWRIGHT_MISSING_MSG,
        )
    s = get_settings()
    to_ms = int(max(5_000, s.nexa_browser_preview_timeout_ms or 35_000))
    _ensure_preview_dir()
    shot_name = f"{uuid.uuid4().hex[:12]}.png"
    out_path = PREVIEW_DIR / shot_name
    title = ""
    final = u
    body_text = ""
    try:
        with spw() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    user_agent=s.nexa_web_user_agent,
                    java_script_enabled=True,
                )
                page = context.new_page()
                page.set_default_timeout(to_ms)
                # networkidle can hang on long-poll sites; use domcontentloaded + short settle
                page.goto(
                    u,
                    wait_until="domcontentloaded",
                    timeout=to_ms,
                )
                page.wait_for_timeout(1_200)
                final = str(page.url)
                title = (page.title() or "")[:2_000]
                html = page.content() or ""
                body_text = extract_visible_text(html, max_chars=12_000) or ""
                try:
                    page.screenshot(path=str(out_path), full_page=False)
                except Exception as e:  # noqa: BLE001
                    logger.info("browser_preview screenshot skipped: %s", type(e).__name__)
            finally:
                browser.close()
    except Exception as e:  # noqa: BLE001
        logger.info("browser_preview error: %s", type(e).__name__)
        return BrowserPreviewResult(
            False,
            u,
            error=f"browser: {e!s}"[:1_200],
            user_message=(
                f"I could not load that page in the headless browser ({type(e).__name__}). "
                "The site may block automation or need a long wait; try a direct public URL again."
            ),
        )

    if len((body_text or "").strip()) < _MIN_TEXT_CHARS and not (title or "").strip():
        return BrowserPreviewResult(
            False,
            final,
            title=title,
            text=body_text,
            error="empty",
            user_message="The page rendered, but I could not read any visible text (empty or blocked).",
        )
    return BrowserPreviewResult(
        True,
        final,
        title=title or "(no title)",
        text=body_text[:10_000],
        screenshot_path=str(out_path) if out_path.is_file() else "",
        user_message="",
    )


def format_preview_for_chat(res: BrowserPreviewResult, *, include_screenshot: bool = True) -> str:
    if not res.ok:
        return res.user_message or (res.error or "browser preview failed")
    lines: list[str] = [
        f"**Page:** {res.title}",
        f"**Final URL:** {res.final_url}",
    ]
    if res.text and res.text.strip():
        lines += ["**Visible text (from browser):**", (res.text or "")[:6_000]]
    if include_screenshot and (res.screenshot_path or "").strip():
        sp = (res.screenshot_path or "").strip()
        if sp:
            lines.append(f"**Screenshot saved (on host):** `{_s('file://' + sp)[:500]}`")
    return "\n\n".join(lines)[:9_000]


def is_static_fetch_likely_too_little(visible_text: str) -> bool:
    """Heuristic: suggest browser preview to owner (short text, may be JS shell)."""
    t = (visible_text or "").strip()
    if len(t) < 400:
        return True
    return False
