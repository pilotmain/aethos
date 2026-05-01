"""SMTP outbound for email channel replies."""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings
from app.services.channel_gateway.rate_limit import acquire_outbound_slot
from app.services.channel_gateway.retry import outbound_with_retry

logger = logging.getLogger(__name__)


def send_smtp_email(
    *,
    to_addr: str,
    subject: str,
    body: str,
    from_addr: str | None = None,
    rate_limit_user_id: str | None = None,
) -> None:
    """
    Send a plain-text email. Uses :envvar:`SMTP_HOST` / :envvar:`SMTP_PORT` / auth from settings.
    """
    acquire_outbound_slot(channel="email", user_id=rate_limit_user_id)

    def _send() -> None:
        s = get_settings()
        host = (s.smtp_host or "").strip()
        if not host:
            raise RuntimeError("SMTP is not configured (SMTP_HOST)")
        from_final = (from_addr or s.email_from or s.smtp_user or "").strip()
        if not from_final:
            raise RuntimeError("Email sender not configured (EMAIL_FROM or SMTP_USER)")
        to_clean = (to_addr or "").strip()
        if not to_clean:
            raise ValueError("missing recipient address")

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_final
        msg["To"] = to_clean
        msg.set_content(body)

        port = int(s.smtp_port or 587)
        user = (s.smtp_user or "").strip()
        password = (s.smtp_password or "").strip()

        if port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context) as smtp:
                if user and password is not None:
                    smtp.login(user, password)
                smtp.send_message(msg)
            return

        with smtplib.SMTP(host, port) as smtp:
            smtp.ehlo()
            if smtp.has_extn("starttls"):
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if user and password is not None:
                smtp.login(user, password)
            smtp.send_message(msg)
        logger.info("smtp sent subject=%r to=%r", subject[:80], to_clean[:80])

    outbound_with_retry(channel="email", operation="smtp_send", func=_send)
