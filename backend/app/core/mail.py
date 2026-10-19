"""Optional outgoing email over SMTP (stdlib smtplib, run in a thread).

Email is off unless SMTP_HOST and SMTP_FROM are set; callers check
`mail_enabled()` and fall back to copyable links (see auth password reset).
"""

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def mail_enabled(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.smtp_host and settings.smtp_from)


def _send_sync(message: EmailMessage, settings: Settings) -> None:
    assert settings.smtp_host is not None
    context = ssl.create_default_context()
    if settings.smtp_security == "ssl":
        smtp: smtplib.SMTP = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context, timeout=20)
    else:
        smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
    with smtp:
        if settings.smtp_security == "starttls":
            smtp.starttls(context=context)
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(message)


async def send_email(to: str, subject: str, body: str) -> bool:
    """Sends a plain-text email. Returns False (and logs) instead of raising,
    since it runs as a background task after the response has gone out."""
    settings = get_settings()
    if not mail_enabled(settings):
        return False
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        await asyncio.to_thread(_send_sync, message, settings)
    except (OSError, smtplib.SMTPException):
        logger.exception("Sending email to %s failed", to)
        return False
    return True
