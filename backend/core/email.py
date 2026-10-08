import logging
import os
import smtplib
from email.message import EmailMessage

# uvicorn's logger, so the INFO lines show in `docker compose logs backend`
logger = logging.getLogger("uvicorn.error")


class EmailSendError(Exception):
    """Raised when the SMTP server could not be reached or refused the email."""


def send_email(to: str, subject: str, body: str) -> None:
    """Send a plain-text email using the SMTP settings from .env.

    - SMTP_HOST empty: nothing is sent, the email is written to the log (dev only).
    - Otherwise it connects to SMTP_HOST:SMTP_PORT (Mailpit in dev, a real server later).
    Raises EmailSendError if sending fails.
    """
    host = os.getenv("SMTP_HOST", "")

    if not host:
        logger.info("EMAIL (not sent, SMTP_HOST is empty) to=%s subject=%s\n%s", to, subject, body)
        return

    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_FROM", "Helpdesk <no-reply@helpdesk.local>")
    use_tls = os.getenv("SMTP_USE_TLS", "false").lower() == "true"

    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            if use_tls:
                smtp.starttls()
            if user:
                smtp.login(user, password)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("Could not send email to %s: %s", to, exc)
        raise EmailSendError("Could not send email") from exc