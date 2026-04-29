import logging
import time
import uuid

import httpx

logger = logging.getLogger(__name__)


class JivoClient:
    """Client for Jivo Bot API outgoing events."""

    def __init__(self, api_url: str, provider_id: str, bot_token: str):
        self.api_url = api_url.rstrip("/")
        self.provider_id = provider_id
        self.bot_token = bot_token

    @property
    def endpoint(self) -> str:
        if not self.provider_id or not self.bot_token:
            raise ValueError("JIVO_PROVIDER_ID and JIVO_BOT_TOKEN must be configured")
        return f"{self.api_url}/webhooks/{self.provider_id}/{self.bot_token}"

    async def send_message(self, client_id: str, chat_id: str, text: str) -> bool:
        payload = {
            "id": str(uuid.uuid4()),
            "client_id": str(client_id),
            "chat_id": str(chat_id),
            "message": {
                "type": "TEXT",
                "text": text,
                "timestamp": int(time.time()),
            },
            "event": "BOT_MESSAGE",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.endpoint, json=payload, timeout=3.0)
                response.raise_for_status()
                logger.info("Sent bot message to Jivo chat %s", chat_id)
                return True
            except (ValueError, httpx.HTTPError) as exc:
                logger.error("Failed to send bot message to Jivo: %s", exc)
                return False

    async def transfer_to_operator(self, client_id: str, chat_id: str) -> bool:
        payload = {
            "id": str(uuid.uuid4()),
            "client_id": str(client_id),
            "chat_id": str(chat_id),
            "event": "INVITE_AGENT",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.endpoint, json=payload, timeout=3.0)
                response.raise_for_status()
                logger.info("Invited agent to Jivo chat %s", chat_id)
                return True
            except (ValueError, httpx.HTTPError) as exc:
                logger.error("Failed to invite Jivo agent: %s", exc)
                return False
