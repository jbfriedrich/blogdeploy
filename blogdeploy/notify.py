"""SMTP failure notifications, sent over SMTP_SSL using the SMTP_* config."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import SMTPConfig


def format_email(blog_key: str, step: str, detail: str, smtp: SMTPConfig,
                 *, success: bool = False) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = smtp.sender
    msg["To"] = smtp.recipient
    if success:
        msg["Subject"] = f"[blogdeploy] {blog_key} deploy succeeded"
        msg.set_content(f"Deploy of '{blog_key}' succeeded.\n\n{detail}\n")
    else:
        msg["Subject"] = f"[blogdeploy] {blog_key} deploy failed at '{step}'"
        msg.set_content(
            f"Deploy of '{blog_key}' failed.\n\n"
            f"Step: {step}\n\n"
            f"Detail:\n{detail}\n"
        )
    return msg


def send_email(msg: EmailMessage, smtp: SMTPConfig) -> None:
    with smtplib.SMTP_SSL(smtp.host, smtp.port) as s:
        s.login(smtp.user, smtp.password)
        s.send_message(msg)
