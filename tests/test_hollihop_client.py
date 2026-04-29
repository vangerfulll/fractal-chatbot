import asyncio
import unittest

from hollihop_client import HollihopClient


class HollihopClientTests(unittest.TestCase):
    def test_mock_client_returns_groups_and_creates_lead(self):
        async def scenario():
            client = HollihopClient("https://example.hollihop.ru/", "MOCK_KEY")
            locations = await client.get_locations("математика", "3 класс")
            groups = await client.get_groups_for_location("математика", "3 класс", "Онлайн")
            created = await client.create_lead("Иван", "79990000000", "Ребенок", 101, "test")

            self.assertIn("Онлайн", locations)
            self.assertEqual(groups[0]["id"], 101)
            self.assertTrue(created)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
