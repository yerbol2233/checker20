"""
SourceMapAgent — формирует план сбора данных для конкретной компании.

Определяет какие коллекторы запускать на основе:
- домена, имени компании, наличия LinkedIn ЛПР URL
- классификации ниши через Gemini Flash (опционально)

Возвращает CollectionPlan — упорядоченный список коллекторов с контекстом.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Базовые коллекторы — всегда запускаются
BASE_COLLECTORS = [
    "website",
    "linkedin_company",
    "glassdoor",
    "crunchbase",
    "g2",
    "indeed",
    "duckduckgo",
    "builtwith",
    "similarweb",
    "apollo",
    "reddit",
    "trustpilot",
    "twitter",
    "capterra",
    "google_reviews",
    "yelp",
    "youtube",
]

# Дополнительные коллекторы по условию
CONDITIONAL_COLLECTORS = {
    "linkedin_person": lambda ctx: bool(ctx.get("linkedin_lpr_url")),
    "sec_edgar": lambda ctx: ctx.get("is_public", False),
}


@dataclass
class CollectionPlan:
    collectors: list[str]             # имена коллекторов для запуска
    context: dict                     # контекст для всех коллекторов
    niche: str = ""                   # классифицированная ниша (Gemini)
    niche_adapted_queries: dict = field(default_factory=dict)

    def includes(self, name: str) -> bool:
        return name in self.collectors


class SourceMapAgent:
    """Агент карты источников — строит план параллельного сбора данных."""

    def __init__(self):
        self._router = None

    def _get_router(self):
        if self._router is None:
            from llm.router import get_llm_router
            self._router = get_llm_router()
        return self._router

    async def build_collection_plan(
        self,
        website_url: str,
        company_name: Optional[str] = None,
        linkedin_lpr_url: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> CollectionPlan:
        """Построить план сбора данных."""
        from collectors.base import BaseCollector

        # Нормализуем домен
        domain = BaseCollector.extract_domain(website_url) if website_url else ""
        resolved_name = company_name or domain

        context = {
            "website_url": website_url,
            "company_name": resolved_name,
            "resolved_company_name": resolved_name,
            "resolved_domain": domain,
            "linkedin_lpr_url": linkedin_lpr_url,
            "is_public": False,  # будет обновлено после SEC EDGAR
        }

        # Базовый набор
        collectors = list(BASE_COLLECTORS)

        # Условные коллекторы
        for name, condition in CONDITIONAL_COLLECTORS.items():
            if condition(context) and name not in collectors:
                collectors.append(name)

        # Классифицируем нишу (опционально — не критично)
        niche = ""
        try:
            niche = await self._classify_niche(
                company_name=resolved_name,
                domain=domain,
                session_id=session_id,
            )
        except Exception as exc:
            logger.debug(f"Niche classification skipped: {exc}")

        logger.info(
            f"CollectionPlan built: {len(collectors)} collectors, "
            f"domain={domain}, niche={niche or 'unknown'}"
        )

        return CollectionPlan(
            collectors=collectors,
            context=context,
            niche=niche,
        )

    async def _classify_niche(
        self,
        company_name: str,
        domain: str,
        session_id: Optional[str] = None,
    ) -> str:
        """Классифицировать нишу компании через Gemini Flash."""
        from llm.base import TaskType

        router = self._get_router()
        prompt = (
            f"Classify the business niche for company '{company_name}' (domain: {domain}).\n"
            f"Choose ONE from: SaaS, FinTech, HealthTech, EdTech, eCommerce, "
            f"MarketingTech, SalesTech, HR Tech, Legal Tech, Real Estate, "
            f"Insurance, Retail, Manufacturing, Other.\n"
            f"Respond with ONLY the category name."
        )
        response = await router.complete(
            task_type=TaskType.NICHE_CLASSIFICATION,
            prompt=prompt,
            max_tokens=20,
            temperature=0.1,
            session_id=session_id,
            agent_name="source_map",
        )
        return response.content.strip()
