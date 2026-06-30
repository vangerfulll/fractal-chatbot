import logging
import re
from typing import Any, Dict, Tuple

import phonenumbers

from hollihop_client import HollihopClient

logger = logging.getLogger(__name__)


class DialogManager:
    def __init__(self, hollihop_api: HollihopClient):
        self.hollihop = hollihop_api

    def _normalize_phone(self, text: str) -> str | None:
        try:
            phone = phonenumbers.parse(text, "RU")
        except phonenumbers.NumberParseException:
            return None

        if not phonenumbers.is_valid_number(phone):
            return None

        return phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.E164)

    def _select_group(self, text: str, groups: list[Dict[str, Any]]) -> Dict[str, Any] | None:
        clean_text = text.strip().lower()
        number_match = re.search(r"\d+", clean_text)

        if number_match:
            idx = int(number_match.group()) - 1
            if 0 <= idx < len(groups):
                return groups[idx]

        for group in groups:
            schedule = str(group.get("schedule", "")).lower()
            name = str(group.get("name", "")).lower()
            if clean_text and (clean_text in schedule or clean_text in name):
                return group

        return None

    async def process(self, text: str, rasa_resp: Dict[str, Any], session: Dict[str, Any]) -> Tuple[str, bool, bool]:
        intent = rasa_resp.get("intent", {}).get("name", "None")
        entities = rasa_resp.get("entities", [])

        for ent in entities:
            ent_name = ent.get("entity")
            ent_val = ent.get("value")
            if ent_name in ["discipline", "grade", "location"]:
                session[ent_name] = ent_val

        state = session.get("state", "IDLE")

        if intent == "request_operator":
            return "Переводим на оператора...", True, False

        if intent == "ask_faq_camps":
            session["state"] = "IDLE"
            return "У нас есть выездные и городские смены. Подробности: fractalclub.ru/camps", False, False

        if intent == "ask_enroll" and state == "IDLE":
            session["state"] = "AWAITING_GRADE_OR_DISCIPLINE"
            state = "AWAITING_GRADE_OR_DISCIPLINE"

        if state == "AWAITING_GRADE_OR_DISCIPLINE":
            discipline = session.get("discipline")
            grade = session.get("grade")

            if not discipline and not grade:
                return "Отлично! Какой предмет вас интересует и для какого класса?", False, False
            if not discipline:
                return "Понял вас. А какой предмет вам больше интересен?", False, False
            if not grade:
                return "Хорошо. А в каком классе учится ребенок?", False, False

            session["state"] = "AWAITING_LOCATION"
            state = "AWAITING_LOCATION"

        if state == "AWAITING_LOCATION":
            discipline = session.get("discipline")
            grade = session.get("grade")
            locations = await self.hollihop.get_locations(discipline, grade)

            if not locations:
                session["state"] = "IDLE"
                return (
                    f"К сожалению, сейчас нет доступных площадок по запросу: {discipline}, {grade}. "
                    "Оставьте контакт, мы вам перезвоним.",
                    True,
                    False,
                )

            session["state"] = "AWAITING_GROUP"
            loc_list = ", ".join(locations)
            return (
                f"Мы нашли площадки для {discipline} ({grade}): {loc_list}. "
                "Какая вам удобнее всего?",
                False,
                False,
            )

        if state == "AWAITING_GROUP":
            location = session.get("location")
            if not location:
                session["location"] = text
                location = text

            groups = await self.hollihop.get_groups_for_location(
                session.get("discipline"),
                session.get("grade"),
                location,
            )

            if not groups:
                return f"На площадке {location} пока не найдено групп. Попробуем другую?", False, False

            reply = "Отлично! Вот доступные группы:\n"
            for idx, group in enumerate(groups, 1):
                reply += f"{idx}. {group['name']} ({group['schedule']}) - мест: {group['vacancy']}\n"
            reply += "\nНапишите номер группы или время, которое вам подходит."

            session["available_groups"] = groups
            session["state"] = "AWAITING_GROUP_SELECTION"
            return reply, False, False

        if state == "AWAITING_GROUP_SELECTION":
            groups = session.get("available_groups", [])
            selected_group = self._select_group(text, groups)

            if not selected_group:
                return (
                    "Не смог определить группу. Напишите, пожалуйста, номер группы из списка "
                    "или время занятия.",
                    False,
                    False,
                )

            session["group_id"] = selected_group["id"]
            session["group_name"] = selected_group.get("name")
            session["group_schedule"] = selected_group.get("schedule")
            session["state"] = "AWAITING_NAME"
            return (
                "Отлично, группу зафиксировал. Напишите, пожалуйста, как к вам обращаться.",
                False,
                False,
            )

        if state == "AWAITING_NAME":
            session["parent_name"] = text
            session["state"] = "AWAITING_PHONE"
            return f"Очень приятно, {text}! Оставьте, пожалуйста, ваш номер телефона.", False, False

        if state == "AWAITING_PHONE":
            phone = self._normalize_phone(text)
            if phone:
                session["phone"] = phone
                success = await self.hollihop.create_lead(
                    name=session.get("parent_name", "Родитель из чата"),
                    phone=session["phone"],
                    child_name="Ребенок (уточнить)",
                    group_id=session.get("group_id", 0),
                    comment=(
                        "Заявка через JivoSite бота. "
                        f"Группа: {session.get('group_name', 'не выбрана')}, "
                        f"расписание: {session.get('group_schedule', 'не выбрано')}"
                    ),
                )
                session["state"] = "IDLE"

                if success:
                    return (
                        "Спасибо! Ваша карточка успешно создана в CRM. "
                        "Администратор свяжется с вами в течение дня.",
                        False,
                        True,
                    )
                return "Спасибо! Заявка принята, мы перезвоним вам в ближайшее время.", True, True

            return "Не похоже на номер телефона. Пожалуйста, напишите номер в формате +7XXXXXXXXXX.", False, False

        if intent == "greet":
            return (
                "Здравствуйте! Я помощник клуба «Фрактал». Хотите записаться в группу "
                "или узнать о лагерях?",
                False,
                False,
            )

        return (
            "Не совсем понял вас. Вы можете спросить про запись в кружок или про наши лагеря. "
            "Позвать оператора?",
            False,
            False,
        )
