import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailGateway:

    def __init__(self) -> None:
        settings = get_settings()
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.use_tls = settings.SMTP_USE_TLS
        self.user = settings.SMTP_USER
        self.password = settings.SMTP_PASSWORD

    async def send_html_email(self, from_email: str, to_email: str, subject: str, body: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        msg.attach(MIMEText(body, "html", "utf-8"))
        await self._send(msg)

    async def send_text_email(self, from_email: str, to_email: str, subject: str, body: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        msg.attach(MIMEText(body, "plain", "utf-8"))
        await self._send(msg)

    async def _send(self, msg: MIMEMultipart) -> None:
        try:
            kwargs: dict = {"hostname": self.host, "port": self.port}
            if self.use_tls:
                kwargs["use_tls"] = True
            if self.user:
                kwargs["username"] = self.user
                kwargs["password"] = self.password

            await aiosmtplib.send(msg, **kwargs)
            logger.info(f"Email sent to {msg['To']}")
        except Exception as e:
            logger.error(f"Failed to send email to {msg['To']}: {e}")
            raise
