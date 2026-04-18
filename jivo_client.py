import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class JivoClient:
    """
    Клиент для взаимодействия с Bot API платформы JivoSite.
    Позволяет отправлять сообщения в чат клиенту и переводить диалог на живого человека.
    """
    def __init__(self, api_url: str, bot_token: str):
        # https://bot.jivosite.com по умолчанию
        self.api_url = api_url.rstrip('/')
        self.bot_token = bot_token

    async def send_message(self, chat_id: int, text: str) -> bool:
        """
        Метод отправки текстового ответа пользователю в окно чата JivoSite.
        """
        # Эндпоинт отправки сообщений, зависит от API Jivo-ботов
        endpoint = f"{self.api_url}/webhooks/{self.bot_token}"
        payload = {
            "event": "message",
            "chat_id": chat_id,
            "message": {
                "type": "text",
                "text": text
            }
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(endpoint, json=payload, timeout=5.0)
                response.raise_for_status()
                logger.info(f"Отправлено сообщение в чат {chat_id}")
                return True
            except httpx.HTTPError as e:
                logger.error(f"Ошибка при ответе в JivoSite: {e}")
                return False

    async def transfer_to_operator(self, chat_id: int, comment: str = "Требуется помощь оператора") -> bool:
        """
        Переключение диалога на живого оператора. 
        Бот перестает обрабатывать события из этого чата, пока не вернут управление.
        """
        endpoint = f"{self.api_url}/webhooks/{self.bot_token}"
        payload = {
            "event": "invoke",
            "invoke": {
                "command": "transfer",
                "chat_id": chat_id,
                "comment": comment
            }
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(endpoint, json=payload, timeout=5.0)
                response.raise_for_status()
                logger.info(f"Чат {chat_id} переведен на администратора")
                return True
            except httpx.HTTPError as e:
                logger.error(f"Ошибка перевода на оператора: {e}")
                return False
