import redis.asyncio as redis
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SessionManager:
    """
    Класс для управления контекстом чата.
    JivoSite работает по принципу 'прислал сообщение - получил ответ 200'.
    Поэтому чтобы бот 'помнил', что родитель спрашивал минуту назад, 
    мы сохраняем шаги общения (state) в Redis.
    """
    def __init__(self, redis_url: str):
        # Пример: redis://localhost:6379/0
        self.redis_url = redis_url
        self.client = None

    async def connect(self):
        if not self.client:
             self.client = redis.from_url(self.redis_url, decode_responses=True)
             logger.info("Подключились к Redis")

    async def get_session(self, chat_id: str) -> Dict[str, Any]:
        """Получить текущий контекст из Redis по ID чата."""
        await self.connect()
        data = await self.client.get(f"session:{chat_id}")
        if data:
            return json.loads(data)
        # Если сессии нет (новый пользователь)
        return {"step": "init", "collected_data": {}}

    async def save_session(self, chat_id: str, session_data: Dict[str, Any], expire_seconds: int = 3600):
        """Сохранить контекст. По умолчанию удаляется через час неактивности."""
        await self.connect()
        await self.client.set(f"session:{chat_id}", json.dumps(session_data), ex=expire_seconds)
