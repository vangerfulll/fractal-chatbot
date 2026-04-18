import emails
import logging

logger = logging.getLogger(__name__)

class EmailNotifier:
    """
    Класс для отправки уведомлений администраторам площадок 
    напрямую на email через SMTP (например, Yandex / Mail.ru / Gmail).
    """
    def __init__(self, smtp_host: str, smtp_port: int, smtp_user: str, smtp_pass: str, from_email: str):
        self.smtp_options = {
            "host": smtp_host,
            "port": smtp_port,
            "user": smtp_user,
            "password": smtp_pass,
            "tls": True
        }
        self.from_email = from_email

    def send_notification(self, to_email: str, subject: str, chat_history: str, lead_info: str) -> bool:
        """Синхронная отправка письма."""
        html_body = f"""
        <h3>Новое обращение к чат-боту на сайте</h3>
        <p><b>Сводка из диалога:</b> {lead_info}</p>
        <hr>
        <p><b>Полная история чата:</b></p>
        <pre>{chat_history}</pre>
        """
        
        message = emails.html(
            html=html_body,
            subject=subject,
            mail_from=self.from_email
        )
        try:
            r = message.send(to=to_email, smtp=self.smtp_options)
            if r.status_code == 250:
                logger.info(f"Уведомление успешно отправлено на почту {to_email}")
                return True
            else:
                logger.error(f"Ошибка SMTP при отправке письма: {r.status_code}")
                return False
        except Exception as e:
            logger.error(f"Отказ отправки email. Причина: {e}")
            return False
