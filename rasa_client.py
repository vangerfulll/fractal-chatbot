import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class RasaClient:
    """
    HTTP-клиент для взаимодействия с Rasa (запущенной как микросервис).
    Отправляет пользовательский текст в модель для получения интента (смысла) и сущностей.
    """
    def __init__(self, rasa_url: str):
        self.rasa_url = rasa_url.rstrip('/')

    async def parse_message(self, message_id: str, text: str) -> Dict[str, Any]:
        """
        Отправляет запрос на эндпоинт /model/parse. 
        Rasa не будет сама формировать ответ, а только скажет нам, 
        какие сущности (entities) и намерения (intents) распознала.
        """
        endpoint = f"{self.rasa_url}/model/parse"
        payload = {
            "text": text,
            "message_id": str(message_id) # Опционально
        }
        
        async with httpx.AsyncClient() as client:
            try:
                # Rasa NLU парсинг работает быстро, 5 сек таймаут достаточно
                response = await client.post(endpoint, json=payload, timeout=5.0)
                response.raise_for_status()
                data = response.json()
                
                intent = data.get('intent', {}).get('name')
                confidence = data.get('intent', {}).get('confidence', 0.0)
                logger.info(f"Rasa распознала интент '{intent}' с уверенностью {confidence}")
                return data
            except httpx.HTTPError as e:
                logger.error(f"Ошибка связи с сервером Rasa: {e}")
                return {}
