import logging
from html import escape

import emails

logger = logging.getLogger(__name__)


class EmailNotifier:
    def __init__(self, smtp_host: str, smtp_port: int, smtp_user: str, smtp_pass: str, from_email: str):
        self.smtp_options = {
            "host": smtp_host,
            "port": smtp_port,
            "user": smtp_user,
            "password": smtp_pass,
            "tls": True,
        }
        self.from_email = from_email

    def send_notification(self, to_email: str, subject: str, chat_history: str, lead_info: str) -> bool:
        safe_lead_info = escape(lead_info)
        safe_chat_history = escape(chat_history)
        html_body = f"""
        <h3>Новое обращение к чат-боту на сайте</h3>
        <p><b>Сводка из диалога:</b> {safe_lead_info}</p>
        <hr>
        <p><b>Полная история чата:</b></p>
        <pre>{safe_chat_history}</pre>
        """

        message = emails.html(
            html=html_body,
            subject=subject,
            mail_from=self.from_email,
        )
        try:
            result = message.send(to=to_email, smtp=self.smtp_options)
            if result.status_code == 250:
                logger.info("Email notification sent to %s", to_email)
                return True
            logger.error("SMTP returned status %s while sending email", result.status_code)
            return False
        except Exception as exc:
            logger.error("Failed to send email notification: %s", exc)
            return False
