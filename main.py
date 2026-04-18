from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
import logging
import uuid
from jivo_client import JivoClient
from hollihop_client import HollihopClient
from rasa_client import RasaClient
from redis_client import SessionManager
from email_client import EmailNotifier
from dialog_manager import DialogManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Fractal Club Chatbot")

# TODO: Данные ключи должны загружаться из .env (через pydantic-settings)
jivo_api = JivoClient(api_url="https://bot.jivosite.com", bot_token="MOCK_TOKEN")
hollihop_api = HollihopClient(base_url="https://api.hollihop.ru/v2", api_key="MOCK_KEY")
rasa_api = RasaClient(rasa_url="http://localhost:5005")
session_mgr = SessionManager(redis_url="redis://localhost:6379/0")
email_api = EmailNotifier(smtp_host="smtp.yandex.ru", smtp_port=465, smtp_user="test", smtp_pass="pass", from_email="bot@fractalclub.ru")
dialog_mgr = DialogManager(hollihop_api)

async def process_jivo_message(event: dict):
    """
    Фоновая задача обработки входящего сообщения от JivoSite.
    Здесь сообщение передается в Rasa (ИИ), сохраняется контекст и формируется ответ.
    """
    event_name = event.get('event_name')
    chat_id = str(event.get('chat_id'))
    
    if event_name == 'client_message':
        text = event.get('message', {}).get('text', '')
        logger.info(f"Новое сообщение '{text}' из чата {chat_id}")
        
        # 1. Загружаем историю (сессию)
        session = await session_mgr.get_session(chat_id)
        chat_history = session.get("chat_history", "")
        chat_history += f"Клиент: {text}\n"
        
        # 2. Получаем интент от Rasa API
        rasa_resp = await rasa_api.parse_message(str(uuid.uuid4()), text)
        intent = rasa_resp.get('intent', {}).get('name')
        
        # 3. Маршрутизация через DialogManager
        reply_text, should_transfer, lead_created = await dialog_mgr.process(text, rasa_resp, session)

        if should_transfer:
            await jivo_api.transfer_to_operator(int(chat_id), "Перевод из-за отсутствия вариантов или запроса")
            
        if lead_created:
            email_api.send_notification("admin1@fractal.ru", "Новая заявка с чата", chat_history + f"\nКлиент: {text}", "Получен телефон клиента. Заявка отправлена в CRM.")

        # Отправляем ответ клиенту
        if reply_text:
            chat_history += f"Бот: {reply_text}\n"
            await jivo_api.send_message(int(chat_id), reply_text)
            
        # 4. Сохраняем сессию
        session["chat_history"] = chat_history
        await session_mgr.save_session(chat_id, session)

@app.get("/")
async def root():
    return {"message": "Chatbot Webhook Server is running."}

@app.post("/webhook/jivosight")
async def jivosight_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Webhook endpoint для получения событий от JivoSite.
    Задачи обрабатываются в фоне, чтобы JivoSite сразу получил ответ 200 OK.
    """
    payload = await request.json()
    logger.info(f"Получен хук от JivoSite: {payload.get('event_name')}")
    
    # Отправляем обработку диалога в фоновую задачу
    background_tasks.add_task(process_jivo_message, payload)
    
    # JivoSite требует мгновенный ответ
    return JSONResponse(content={"result": "ok"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
