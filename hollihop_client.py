import asyncio
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class HollihopClient:
    """Async adapter around hollihop-api-client."""

    def __init__(self, domain: str, api_key: str):
        self.domain = self._normalize_domain(domain)
        self.api_key = api_key
        self._api = None

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        domain = (domain or "").strip()
        if not domain:
            return ""

        for suffix in ("/Api/V2/", "/Api/V2", "/api/v2/", "/api/v2", "/v2/", "/v2"):
            if domain.endswith(suffix):
                domain = domain[: -len(suffix)]

        if not domain.endswith("/"):
            domain += "/"
        return domain

    @property
    def is_mock(self) -> bool:
        return self.api_key == "MOCK_KEY"

    @property
    def api(self):
        if self._api is None:
            from hollihop_api_client import HolliHopAPI

            self._api = HolliHopAPI(self.domain, self.api_key)
        return self._api

    async def get_locations(self, discipline: str, grade: str) -> List[str]:
        if self.is_mock:
            logger.info("[MOCK] Requesting HolliHop locations for %s, %s", discipline, grade)
            return ["ст. м. Петроградская", "ст. м. Василеостровская", "Онлайн"]

        try:
            units = await asyncio.to_thread(self._get_ed_units, discipline, grade)
        except Exception as exc:
            logger.error("Failed to get HolliHop locations: %s", exc)
            return []

        locations = {
            self._unit_location(unit)
            for unit in units
            if self._unit_location(unit)
        }
        return sorted(locations)

    async def get_groups_for_location(self, discipline: str, grade: str, location: str) -> List[Dict[str, Any]]:
        if self.is_mock:
            logger.info("[MOCK] Requesting HolliHop groups for %s at %s", discipline, location)
            clean_disc = (discipline or "Предмет").capitalize()
            clean_grade = (grade or "").replace(" класс", "").replace("класс", "").strip()
            return [
                {"id": 101, "name": f"{clean_disc} ({clean_grade} класс)", "schedule": "Вт 16:00 - 17:30", "vacancy": 3},
                {"id": 102, "name": f"{clean_disc} (углубл.)", "schedule": "Чт 18:00 - 19:30", "vacancy": 5},
            ]

        try:
            units = await asyncio.to_thread(self._get_ed_units, discipline, grade)
        except Exception as exc:
            logger.error("Failed to get HolliHop groups: %s", exc)
            return []

        normalized_location = location.strip().lower()
        groups = []
        for unit in units:
            unit_location = self._unit_location(unit).lower()
            if normalized_location and normalized_location not in unit_location:
                continue
            groups.append(
                {
                    "id": unit.id,
                    "name": unit.name or "Группа без названия",
                    "schedule": self._format_schedule(unit),
                    "vacancy": unit.vacancies if unit.vacancies is not None else 0,
                }
            )
        return groups

    async def create_lead(self, name: str, phone: str, child_name: str, group_id: int, comment: str) -> bool:
        if self.is_mock:
            logger.info("[MOCK] Created HolliHop lead for %s in group %s", phone, group_id)
            return True

        try:
            lead_id = await asyncio.to_thread(
                self._create_lead_sync,
                name,
                phone,
                child_name,
                group_id,
                comment,
            )
        except Exception as exc:
            logger.error("Failed to create HolliHop lead: %s", exc)
            return False

        logger.info("Created HolliHop lead %s for group %s", lead_id, group_id)
        return True

    def _get_ed_units(self, discipline: str, grade: str):
        kwargs: dict[str, Any] = {
            "types": "Group,MiniGroup",
            "statuses": "Reserve,Forming,Working",
            "query_days": False,
            "query_fiscal_info": False,
            "query_teacher_prices": False,
        }
        if discipline:
            kwargs["disciplines"] = [discipline]
        if grade:
            kwargs["levels"] = [grade]

        return self.api.ed_units.get_ed_units(**kwargs)

    def _create_lead_sync(self, name: str, phone: str, child_name: str, group_id: int, comment: str) -> int | None:
        lead = self.api.leads.add_lead(
            first_name=child_name,
            comment=f"{comment}\nРодитель: {name}\nГруппа: {group_id}",
            ad_source="JivoSite bot",
        )
        lead_id = lead.lead_id
        if lead_id:
            self.api.leads.edit_contacts(lead_id=lead_id, mobile=phone)
        return lead_id

    @staticmethod
    def _unit_location(unit: Any) -> str:
        return (
            getattr(unit, "office_or_company_name", None)
            or getattr(unit, "office_or_company_address", None)
            or ""
        )

    @staticmethod
    def _format_schedule(unit: Any) -> str:
        schedule_items = getattr(unit, "schedule_items", None) or []
        if not schedule_items:
            return "Расписание уточняется"

        parts = []
        for item in schedule_items[:3]:
            begin_time = getattr(item, "begin_time", None)
            end_time = getattr(item, "end_time", None)
            teacher = getattr(item, "teacher", None)
            time_part = f"{begin_time or ''} - {end_time or ''}".strip(" -")
            if teacher:
                parts.append(f"{time_part} ({teacher})" if time_part else str(teacher))
            elif time_part:
                parts.append(time_part)

        return "; ".join(parts) or "Расписание уточняется"
