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


if __name__ == "__main__":
    unittest.main()
