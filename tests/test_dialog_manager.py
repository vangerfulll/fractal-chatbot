import asyncio
import unittest

from dialog_manager import DialogManager


class FakeHollihop:
    async def get_locations(self, discipline, grade):
        return ["Онлайн"]

    async def get_groups_for_location(self, discipline, grade, location):
        return [
            {"id": 101, "name": "Математика", "schedule": "Вт 16:00", "vacancy": 3},
            {"id": 102, "name": "Физика", "schedule": "Чт 18:00", "vacancy": 5},
        ]

    async def create_lead(self, *args, **kwargs):
        return True


class DialogManagerTests(unittest.TestCase):
    def test_selects_group_by_number(self):
        manager = DialogManager(FakeHollihop())
        groups = [
            {"id": 101, "name": "Математика", "schedule": "Вт 16:00", "vacancy": 3},
            {"id": 102, "name": "Физика", "schedule": "Чт 18:00", "vacancy": 5},
        ]

        self.assertEqual(manager._select_group("2", groups)["id"], 102)

    def test_selects_group_by_time(self):
        manager = DialogManager(FakeHollihop())
        groups = [
            {"id": 101, "name": "Математика", "schedule": "Вт 16:00", "vacancy": 3},
            {"id": 102, "name": "Физика", "schedule": "Чт 18:00", "vacancy": 5},
        ]

        self.assertEqual(manager._select_group("18:00", groups)["id"], 102)

    def test_normalizes_valid_phone(self):
        manager = DialogManager(FakeHollihop())

        self.assertEqual(manager._normalize_phone("8 999 123-45-67"), "+79991234567")

    def test_rejects_invalid_phone(self):
        manager = DialogManager(FakeHollihop())

        self.assertIsNone(manager._normalize_phone("1234567"))

    def test_collects_free_text_discipline_without_rasa_entity(self):
        async def scenario():
            manager = DialogManager(FakeHollihop())
            session = {"state": "AWAITING_GRADE_OR_DISCIPLINE"}

            reply, _, _ = await manager.process(
                "олимпиадная геометрия",
                {"intent": {"name": "None"}, "entities": []},
                session,
            )

            self.assertEqual(session["discipline"], "олимпиадная геометрия")
            self.assertEqual(reply, "Хорошо. А в каком классе учится ребенок?")

        asyncio.run(scenario())

    def test_collects_free_text_grade_without_rasa_entity(self):
        async def scenario():
            manager = DialogManager(FakeHollihop())
            session = {"state": "AWAITING_GRADE_OR_DISCIPLINE", "discipline": "олимпиадная геометрия"}

            reply, _, _ = await manager.process(
                "5",
                {"intent": {"name": "None"}, "entities": []},
                session,
            )

            self.assertEqual(session["grade"], "5 класс")
            self.assertIn("Мы нашли площадки", reply)

        asyncio.run(scenario())

    def test_enroll_trigger_is_not_saved_as_discipline(self):
        async def scenario():
            manager = DialogManager(FakeHollihop())
            session = {}

            reply, _, _ = await manager.process(
                "Записаться на занятия",
                {"intent": {"name": "ask_enroll"}, "entities": []},
                session,
            )

            self.assertNotIn("discipline", session)
            self.assertEqual(reply, "Отлично! Какой предмет вас интересует и для какого класса?")

        asyncio.run(scenario())

    def test_false_camp_intent_without_camp_words_does_not_answer_camps(self):
        async def scenario():
            manager = DialogManager(FakeHollihop())
            session = {}

            reply, _, _ = await manager.process(
                "василеостровская",
                {"intent": {"name": "ask_faq_camps"}, "entities": []},
                session,
            )

            self.assertNotIn("fractalclub.ru/camps", reply)

        asyncio.run(scenario())

    def test_real_camp_question_still_answers_camps(self):
        async def scenario():
            manager = DialogManager(FakeHollihop())
            session = {}

            reply, _, _ = await manager.process(
                "какие лагеря есть летом",
                {"intent": {"name": "ask_faq_camps"}, "entities": []},
                session,
            )

            self.assertIn("fractalclub.ru/camps", reply)

        asyncio.run(scenario())

    def test_enroll_flow_reaches_phone_step(self):
        async def scenario():
            manager = DialogManager(FakeHollihop())
            session = {}

            await manager.process(
                "хочу записаться",
                {
                    "intent": {"name": "ask_enroll"},
                    "entities": [
                        {"entity": "discipline", "value": "математика"},
                        {"entity": "grade", "value": "3 класс"},
                    ],
                },
                session,
            )
            await manager.process("Онлайн", {"intent": {"name": "None"}, "entities": []}, session)
            await manager.process("2", {"intent": {"name": "None"}, "entities": []}, session)

            self.assertEqual(session["group_id"], 102)
            self.assertEqual(session["state"], "AWAITING_NAME")

        asyncio.run(scenario())

    def test_active_enroll_flow_ignores_false_camp_intent(self):
        async def scenario():
            manager = DialogManager(FakeHollihop())
            session = {
                "state": "AWAITING_GROUP",
                "discipline": "олимпиадная геометрия",
                "grade": "5 класс",
            }

            reply, should_transfer, lead_created = await manager.process(
                "Василеостровская",
                {"intent": {"name": "ask_faq_camps"}, "entities": []},
                session,
            )

            self.assertIn("Вот доступные группы", reply)
            self.assertFalse(should_transfer)
            self.assertFalse(lead_created)
            self.assertEqual(session["state"], "AWAITING_GROUP_SELECTION")

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
