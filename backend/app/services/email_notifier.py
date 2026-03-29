from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.config import Settings
from app.schemas import AlertRecord

logger = logging.getLogger(__name__)


class EmailNotifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_alert(self, alert: AlertRecord) -> None:
        if not self.settings.email_enabled:
            return

        message = EmailMessage()
        message["From"] = self.settings.smtp_from
        message["To"] = ", ".join(self.settings.smtp_to_list)
        message["Subject"] = f"[Space Weather] {alert.level.upper()} - {alert.title}"
        message.set_content(
            "\n".join(
                [
                    f"Alert ID: {alert.id}",
                    f"Level: {alert.level}",
                    f"Created at: {alert.created_at.isoformat()}",
                    "",
                    alert.message,
                ]
            )
        )

        try:
            await asyncio.to_thread(self._send_sync, message)
        except Exception:
            logger.exception("Failed to send email alert %s", alert.id)

    def _send_sync(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=15) as smtp:
            if self.settings.smtp_username and self.settings.smtp_password:
                smtp.login(self.settings.smtp_username, self.settings.smtp_password)
            smtp.send_message(message)
