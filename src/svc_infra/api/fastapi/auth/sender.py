from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Protocol

from svc_infra.app.env import CURRENT_ENVIRONMENT, PROD_ENV

from .settings import get_auth_settings


class Sender(Protocol):
    def send(self, to: str, subject: str, html_body: str) -> None:
        pass


class ConsoleSender:
    def send(self, to: str, subject: str, html_body: str) -> None:
        print(f"[MAIL -> {to}] {subject}\n{html_body}\n")


class SMTPSender:
    def __init__(self, host: str, port: int, username: str, password: str, from_addr: str) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_addr = from_addr

    def send(self, to: str, subject: str, html_body: str) -> None:
        msg = EmailMessage()
        msg["From"] = self.from_addr
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(html_body, subtype="html")
        with smtplib.SMTP(self.host, self.port) as s:
            s.starttls()
            s.login(self.username, self.password)
            s.send_message(msg)


def get_sender() -> Sender:
    st = get_auth_settings()

    host = st.smtp_host
    user = st.smtp_username
    pw = st.smtp_password.get_secret_value() if st.smtp_password else None
    frm = st.smtp_from

    configured = all([host, user, pw, frm])

    # In prod, hard error if SMTP is not configured.
    if CURRENT_ENVIRONMENT == PROD_ENV and not configured:
        raise RuntimeError(
            "SMTP is required in prod for verification emails. Configure AUTH_SMTP_* envs."
        )

    # Dev fallback: console sender if not configured
    if not configured:
        return ConsoleSender()

    return SMTPSender(host, st.smtp_port, user, pw, frm)
