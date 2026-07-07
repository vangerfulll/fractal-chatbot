import logging
import uuid
import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from dialog_manager import DialogManager
from email_client import EmailNotifier
from hollihop_client import HollihopClient
from jivo_client import JivoClient
from rasa_client import RasaClient
from redis_client import SessionManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_startup_settings() -> None:
    if settings.APP_ENV.lower() == "production" and settings.MOCK_EXTERNAL_APIS:
        raise RuntimeError("MOCK_EXTERNAL_APIS must be false in production")
    if settings.APP_ENV.lower() == "production":
        missing = []
        for name in ("JIVO_PROVIDER_ID", "JIVO_BOT_TOKEN", "HOLLIHOP_DOMAIN", "HOLLIHOP_API_KEY"):
            if not getattr(settings, name):
                missing.append(name)
        if missing:
            raise RuntimeError(f"Missing production settings: {', '.join(missing)}")


validate_startup_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    if session_mgr.client:
        await session_mgr.client.close()
        logger.info("Closed Redis connection pool")

app = FastAPI(title="Fractal Club Chatbot", lifespan=lifespan)

jivo_api = JivoClient(
    api_url=settings.JIVO_API_URL,
    provider_id=settings.JIVO_PROVIDER_ID,
    bot_token=settings.JIVO_BOT_TOKEN,
)
hollihop_api = HollihopClient(
    domain=settings.HOLLIHOP_DOMAIN or settings.HOLLIHOP_API_URL,
    api_key="MOCK_KEY" if settings.MOCK_EXTERNAL_APIS else settings.HOLLIHOP_API_KEY,
)
rasa_api = RasaClient(rasa_url=settings.RASA_URL)
session_mgr = SessionManager(redis_url=settings.REDIS_URL)
email_api = EmailNotifier(
    smtp_host=settings.SMTP_SERVER,
    smtp_port=settings.SMTP_PORT,
    smtp_user=settings.SMTP_USER,
    smtp_pass=settings.SMTP_PASSWORD,
    from_email=settings.SMTP_FROM_EMAIL,
)
dialog_mgr = DialogManager(hollihop_api)


async def process_jivo_message(event: dict) -> bool:
    event_name = event.get("event") or event.get("event_name")
    chat_id = str(event.get("chat_id") or "")
    client_id = str(event.get("client_id") or event.get("sender", {}).get("id") or "")

    if event_name in ("AGENT_UNAVAILABLE", "agent_unavailable"):
        if not chat_id or not client_id:
            logger.warning("Invalid Jivo AGENT_UNAVAILABLE payload: missing chat_id or client_id")
            return True

        session = await session_mgr.get_session(chat_id)
        if session.get("agent_unavailable_greeting_sent"):
            return True

        reply_text = (
            "Здравствуйте! Я помощник клуба «Фрактал». Хотите записаться в группу "
            "или узнать о лагерях?"
        )
        session["agent_unavailable_greeting_sent"] = True
        session["chat_history"] = session.get("chat_history", "") + f"Bot: {reply_text}\n"
        await session_mgr.save_session(chat_id, session)
        return await jivo_api.send_message(client_id, chat_id, reply_text)

    if event_name not in ("CLIENT_MESSAGE", "client_message"):
        logger.info("Unsupported Jivo event ignored: %s", event_name)
        return True

    text = event.get("message", {}).get("text", "")
    if not chat_id or not client_id or not text:
        logger.warning("Invalid Jivo CLIENT_MESSAGE payload: missing chat_id, client_id or text")
        return False

    logger.info("New Jivo message in chat %s", chat_id)

    session = await session_mgr.get_session(chat_id)
    chat_history = session.get("chat_history", "")
    chat_history += f"Client: {text}\n"

    rasa_resp = await rasa_api.parse_message(str(uuid.uuid4()), text)
    reply_text, should_transfer, lead_created = await dialog_mgr.process(text, rasa_resp, session)

    if lead_created and settings.ADMIN_EMAIL:
        await asyncio.to_thread(
            email_api.send_notification,
            settings.ADMIN_EMAIL,
            "New lead from chat",
            chat_history + f"\nClient: {text}",
            "Phone received. Lead was sent to CRM.",
        )

    if reply_text:
        chat_history += f"Bot: {reply_text}\n"
        if not await jivo_api.send_message(client_id, chat_id, reply_text):
            return False

    if should_transfer and not await jivo_api.transfer_to_operator(client_id, chat_id):
        return False

    session["chat_history"] = chat_history
    await session_mgr.save_session(chat_id, session)
    return True


@app.get("/")
async def root():
    return {"message": "Chatbot Webhook Server is running."}


@app.get("/health/live")
async def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    checks = {"redis": False, "rasa": False, "settings": True}

    try:
        await session_mgr.connect()
        await session_mgr.client.ping()
        checks["redis"] = True
    except Exception as exc:
        logger.warning("Redis readiness check failed: %s", exc)

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{settings.RASA_URL.rstrip('/')}/version")
            checks["rasa"] = response.status_code < 500
    except Exception as exc:
        logger.warning("Rasa readiness check failed: %s", exc)

    if not all(checks.values()):
        raise HTTPException(status_code=503, detail=checks)

    return {"status": "ready", "checks": checks}


async def _handle_jivo_webhook(request: Request, token: str):
    if not settings.JIVO_BOT_TOKEN or token != settings.JIVO_BOT_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid Jivo token")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload format")

    logger.info("Received Jivo event: %s", payload.get("event") or payload.get("event_name"))

    if not await process_jivo_message(payload):
        raise HTTPException(status_code=502, detail="Jivo event processing failed")

    return JSONResponse(content={"result": "ok"})


@app.post("/webhook/jivosite/{token}")
async def jivosite_webhook(token: str, request: Request):
    return await _handle_jivo_webhook(request, token)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
