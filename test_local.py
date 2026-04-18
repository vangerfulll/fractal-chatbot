import asyncio
import uuid
from rasa_client import RasaClient
from redis_client import SessionManager
from hollihop_client import HollihopClient
from dialog_manager import DialogManager

rasa_api = RasaClient("http://localhost:5005")
session_mgr = SessionManager("redis://localhost:6379/0")
hollihop_api = HollihopClient(base_url="https://api.hollihop.ru/v2", api_key="MOCK_KEY")
dialog_mgr = DialogManager(hollihop_api)

async def chat():
    chat_id = "test_user_123"
    print("=========================================")
    print("=== ЛОКАЛЬНЫЙ ТЕСТ ЧАТ-БОТА ФРАКТАЛ ===")
    print("=========================================")
    print("Убедитесь, что Rasa и Redis запущены (docker-compose up -d rasa redis)")
    print("Для выхода напишите 'выход'\n")

    while True:
        text = input("Вы: ")
        if text.lower() == 'выход':
            break

        # 1. Загружаем историю (сессию)
        session = await session_mgr.get_session(chat_id)
        chat_history = session.get("chat_history", "")
        chat_history += f"Клиент: {text}\n"

        # 2. Получаем интент от Rasa API
        try:
            rasa_resp = await rasa_api.parse_message(str(uuid.uuid4()), text)
            intent = rasa_resp.get('intent', {}).get('name', 'None')
            confidence = rasa_resp.get('intent', {}).get('confidence', 0.0)
            print(f"  [Система: Rasa поняла смысл как -> '{intent}' (уверенность: {confidence*100:.1f}%)]")
        except Exception as e:
            print(f"  [Система: Не удалось связаться с Rasa (убедитесь что контейнер запущен): {e}]")
            intent = "None"

        # 3. Маршрутизация на основе смысла через DialogManager
        reply_text, should_transfer, lead_created = await dialog_mgr.process(text, rasa_resp, session)

        if should_transfer:
            print("  [Система: Сработал триггер перевода на оператора]")
        if lead_created:
            print("  [Система: Заявка(Лид) создана в Hollihop CRM!]")

        # Отправляем ответ клиенту
        if reply_text:
            chat_history += f"Бот: {reply_text}\n"
            print(f"Бот: {reply_text}\n")

        # 4. Сохраняем сессию
        session["chat_history"] = chat_history
        try:
            await session_mgr.save_session(chat_id, session)
        except Exception as e:
            print(f"  [Система: Ошибка кэша Redis: {e}]")

if __name__ == "__main__":
    asyncio.run(chat())
