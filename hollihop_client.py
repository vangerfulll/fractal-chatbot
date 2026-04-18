import httpx
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class HollihopClient:
    """
    Класс для работы с API Hollihop Schoolmaster.
    Вся логика связи с CRM (расписание, лиды) инкапсулируется здесь.
    """
    def __init__(self, base_url: str, api_key: str):
        # Обычно URL имеет вид https://НАЗВАНИЕ.hollihop.ru/v2
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        # Чаще всего в Hollihop авторизация идет через параметр authkey в запросе
        self.default_params = {
            "authkey": self.api_key
        }

    async def get_locations(self, discipline: str, grade: str) -> List[str]:
        """
        Метод для получения списка уникальных площадок для заданного предмета и возраста.
        В боевой версии делает реальный запрос в Hollihop GetEdUnits и парсит уникальные LocationName.
        """
        # Если используется заглушка, возвращаем тестовые данные
        if self.api_key == "MOCK_KEY":
            logger.info(f"[MOCK] Запрос площадок для: {discipline}, {grade}")
            return ["ст. м. Петроградская", "ст. м. Василеостровская", "Онлайн"]
            
        endpoint = f"{self.base_url}/Api/GetEdUnits"
        params = self.default_params.copy()
        params["Discipline"] = discipline
        # В реальном API Hollihop нужно будет передавать параметры возраста/уровня по их документации
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(endpoint, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                units = data.get("EdUnits", [])
                
                # Извлекаем уникальные площадки
                locations = set()
                for unit in units:
                    loc = unit.get("LocationName")
                    if loc:
                        locations.add(loc)
                return list(locations)
            except httpx.HTTPError as e:
                logger.error(f"Ошибка при запросе расписания Hollihop: {e}")
                return []

    async def get_groups_for_location(self, discipline: str, grade: str, location: str) -> List[Dict[str, Any]]:
        """
        Метод для получения расписания (групп) по конкретному предмету и площадке.
        """
        if self.api_key == "MOCK_KEY":
            logger.info(f"[MOCK] Запрос групп для {discipline} на площадке {location}")
            # Небольшая эвристика для красивых падежей в тестовых данных (математику -> Математика)
            clean_disc = discipline.replace("у", "а").capitalize()
            # Убираем дублирование слова "класс"
            clean_grade = grade.replace(" класс", "").replace("класс", "").strip()
            
            return [
                {"id": 101, "name": f"{clean_disc} ({clean_grade} класс)", "schedule": "Вт 16:00 - 17:30", "vacancy": 3},
                {"id": 102, "name": f"{clean_disc} (углубл.)", "schedule": "Чт 18:00 - 19:30", "vacancy": 5}
            ]

            
        endpoint = f"{self.base_url}/Api/GetEdUnits"
        params = self.default_params.copy()
        params["Discipline"] = discipline
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(endpoint, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                units = data.get("EdUnits", [])
                
                # Фильтруем по расписанию и наличию мест
                valid_groups = []
                for unit in units:
                    if unit.get("LocationName") == location:
                        # Примерная структура, зависит от реального ответа вашей CRM
                        valid_groups.append({
                            "id": unit.get("Id"),
                            "name": unit.get("Name"),
                            "schedule": unit.get("ScheduleDescription", "Расписание уточняется"),
                            "vacancy": unit.get("Vacancy", 0)
                        })
                return valid_groups
            except httpx.HTTPError as e:
                logger.error(f"Ошибка при запросе групп Hollihop: {e}")
                return []

    async def create_lead(self, name: str, phone: str, child_name: str, group_id: int, comment: str) -> bool:
        """
        Метод для создания новой заявки (лида/ученика) на наборы.
        Обычно используется эндпоинт AddStudent / AddLead.
        """
        endpoint = f"{self.base_url}/Api/AddStudent"
        
        params = self.default_params.copy()
        payload = {
            "FirstName": child_name,
            "ParentName": name,
            "Mobile": phone,
            "EdUnitId": group_id, # ID группы, куда записались
            "Note": comment       # Комментарий с историей чата
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(endpoint, params=params, json=payload, timeout=10.0)
                response.raise_for_status()
                logger.info(f"Заявка для {phone} успешно отправлена в Hollihop")
                return True
            except httpx.HTTPError as e:
                logger.error(f"Ошибка при создании заявки в Hollihop: {e}")
                return False

# Инициализация будет в main.py после загрузки .env переменных
# hollihop_api = HollihopClient(base_url="https://myclub.hollihop.ru", api_key="KEY")
