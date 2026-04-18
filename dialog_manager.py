import logging
from typing import Dict, Any, Tuple
from hollihop_client import HollihopClient

logger = logging.getLogger(__name__)

class DialogManager:
    def __init__(self, hollihop_api: HollihopClient):
        self.hollihop = hollihop_api

    async def process(self, text: str, rasa_resp: Dict[str, Any], session: Dict[str, Any]) -> Tuple[str, bool, bool]:
        """
        Обрабатывает шаг диалога.
        Возвращает:
        - reply_text (str): Текст для ответа пользователю
        - transfer_to_operator (bool): Нужно ли перевести на оператора
        - lead_created (bool): Был ли только что создан лид (для отправки уведомления)
        """
        intent = rasa_resp.get('intent', {}).get('name', 'None')
        entities = rasa_resp.get('entities', [])
        
        # Обновляем данные сессии из найденных сущностей при каждом сообщении
        for ent in entities:
            ent_name = ent.get("entity")
            ent_val = ent.get("value")
            if ent_name in ["discipline", "grade", "location"]:
                session[ent_name] = ent_val

        state = session.get("state", "IDLE")
        reply_text = ""
        should_transfer = False
        lead_created = False

        # --- ГЛОБАЛЬНЫЕ ИНТЕНТЫ ---
        if intent == "request_operator":
            return "Переводим на оператора...", True, False

        if intent == "ask_faq_camps":
            session["state"] = "IDLE"
            return "У нас множество выездных и городских смен! Вся документация на сайте fractalclub.ru/camps", False, False

        if intent == "ask_enroll" and state == "IDLE":
            session["state"] = "AWAITING_GRADE_OR_DISCIPLINE"
            state = "AWAITING_GRADE_OR_DISCIPLINE"

        # --- STATE MACHINE ВОРОНКИ ---
        
        if state == "AWAITING_GRADE_OR_DISCIPLINE":
            discipline = session.get("discipline")
            grade = session.get("grade")
            
            if not discipline and not grade:
                return "Отлично! Какой предмет вас интересует (математика, физика, программирование) и для какого класса?", False, False
            elif not discipline:
                return "Понял вас. А какой предмет вам больше интересен?", False, False
            elif not grade:
                return "Хорошо. А в каком классе учится ребенок?", False, False
            else:
                # Все данные собраны, переходим к поиску площадок
                session["state"] = "AWAITING_LOCATION"
                state = "AWAITING_LOCATION"
                
        if state == "AWAITING_LOCATION":
            discipline = session.get("discipline")
            grade = session.get("grade")
            locations = await self.hollihop.get_locations(discipline, grade)
            
            if not locations:
                session["state"] = "IDLE"
                return f"К сожалению, сейчас нет доступных площадок по запросу: {discipline} для {grade} класса. Оставьте контакт, мы вам перезвоним!", True, False
                
            loc_list = ", ".join(locations)
            session["state"] = "AWAITING_GROUP"
            return f"Мы нашли следующие площадки для {discipline} ({grade} класс): {loc_list}. Какая вам удобнее всего?", False, False

        if state == "AWAITING_GROUP":
            location = session.get("location")
            # Если Rasa выцепила локацию
            if not location:
                # Эвристика: если пользователь просто написал название в ответ, запишем его
                session["location"] = text
                location = text
                
            groups = await self.hollihop.get_groups_for_location(session.get("discipline"), session.get("grade"), location)
            
            if not groups:
                return f"На площадке {location} пока не найдено групп. Попробуем другую?", False, False
                
            reply = "Отлично! Вот доступные группы:\n"
            for idx, g in enumerate(groups, 1):
                reply += f"{idx}. {g['name']} ({g['schedule']}) - мест: {g['vacancy']}\n"
            reply += "\nНапишите номер группы или время, которое вам подходит."
            session["state"] = "AWAITING_NAME"
            # Сохраняем первую группу по умолчанию для демо-записи, так как нужен сложный парсер выбора
            session["group_id"] = groups[0]["id"] 
            return reply + "\nОпределились? Тогда напишите, пожалуйста, как к вам обращаться (Ваше Имя).", False, False

        if state == "AWAITING_NAME":
            session["parent_name"] = text
            session["state"] = "AWAITING_PHONE"
            return f"Очень приятно, {text}! И последний шаг: оставьте ваш номер телефона.", False, False

        if state == "AWAITING_PHONE":
            # Простой парсинг контакта. Если содержит цифры - считаем телефоном
            if any(char.isdigit() for char in text) and len(text) > 6:
                session["phone"] = text
                success = await self.hollihop.create_lead(
                    name=session.get("parent_name", "Родитель из чата"),
                    phone=session["phone"],
                    child_name="Ребенок (уточнить)",
                    group_id=session.get("group_id", 0),
                    comment="Заявка через JivoSite бота"
                )
                session["state"] = "IDLE"
                
                if success:
                    return "Спасибо! Ваша карточка успешно создана в CRM. Администратор свяжется с вами в течение дня.", False, True
                else:
                    return "Спасибо! Заявка принята, мы перезвоним вам в ближайшее время.", True, True
            else:
                return "Хм, не похоже на номер телефона. Пожалуйста, напишите телефон цифрами.", False, False

        # Если стейт IDLE и интент не понятен
        if intent == "greet":
            return "Здравствуйте! Я интеллектуальный помощник клуба «Фрактал». Хотите записаться в группу или узнать о лагерях?", False, False
            
        return "Не совсем понял вас. Вы можете спросить про запись в кружок или про наши лагеря. Позвать оператора?", False, False
