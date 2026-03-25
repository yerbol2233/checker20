"""
PassportGeneratorAgent — генерирует паспорт компании (11 блоков) на русском.

Правила (CLAUDE.md + ТЗ):
- Язык: СТРОГО РУССКИЙ
- Факты: только с источником
- Гипотезы: ⚠️ Гипотеза:
- Нет данных: "Данные не найдены"
- Никогда не выдумывать данные
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from agents.prioritizer import PrioritizedData
from llm.base import TaskType

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_BASE = """Ты составляешь паспорт компании для B2B sales-менеджера.
Язык: СТРОГО РУССКИЙ.
Правила:
- Факты: только с указанием источника в скобках (LinkedIn, Glassdoor, etc.)
- Гипотезы: помечать ⚠️ Гипотеза:
- Нет данных: писать "Данные не найдены"
- Без выдумок, без обобщений без источника
- Быть конкретным, избегать общих слов
Отвечай ТОЛЬКО валидным JSON."""

BLOCK_PROMPTS = {
    1: ("Общий профиль компании",
        "company_name, website, headquarters, niche, product_description, business_model, "
        "target_customers, employees_count, revenue_estimate, stage, funding_rounds, "
        "linkedin_followers, twitter_followers"),
    2: ("Модель продаж",
        "sales_team_exists, sales_channels, avg_deal_size, tools_used, "
        "sales_process_signals, hypotheses_about_funnel"),
    3: ("Потенциальные боли в продажах",
        "pains_list (каждая: pain, fact, hypothesis, confidence, source)"),
    4: ("Ключевые люди",
        "founders, key_executives, decision_makers, hiring_signals"),
    5: ("Контекст и зацепки",
        "recent_news, company_posts, notable_events, hooks"),
    6: ("Конкурентная среда",
        "direct_competitors, indirect_competitors, market_position"),
    7: ("Готовность к покупке",
        "score, level, factors, verdict"),
    8: ("Репутация и отзывы",
        "overall_rating, reviews_summary, positive_signals, negative_signals, "
        "review_sources"),
    9: ("Триггеры входа",
        "positive_triggers, negative_triggers, seasonality, verdict"),
    10: ("Профиль ЛПР",
        "name, title, company, background, linkedin_activity, profile_type, "
        "overheating_score, best_outreach_angle"),
    11: ("Контекст отрасли",
        "industry, trends, market_size, growth_signals"),
}


class PassportGeneratorAgent:
    """Генератор паспорта компании — 11 блоков на русском."""

    def __init__(self):
        self._router = None

    def _get_router(self):
        if self._router is None:
            from llm.router import get_llm_router
            self._router = get_llm_router()
        return self._router

    async def generate(
        self,
        prioritized: PrioritizedData,
        context: dict,
        session_id: Optional[str] = None,
    ):
        """Генерировать полный паспорт и сохранить в БД."""
        from models.passport import Passport

        company_name = context.get("company_name", "Unknown")
        results = prioritized.cleaned_data.results_by_source
        analysis = prioritized.analysis

        # Генерируем каждый блок
        blocks = {}
        import asyncio

        # Параллельная генерация блоков
        block_tasks = {}
        for block_num in range(1, 12):
            block_tasks[block_num] = asyncio.create_task(
                self._generate_block(
                    block_num=block_num,
                    company_name=company_name,
                    results=results,
                    analysis=analysis,
                    prioritized=prioritized,
                    session_id=session_id,
                )
            )

        for block_num, task in block_tasks.items():
            try:
                blocks[block_num] = await task
            except Exception as exc:
                logger.warning(f"Block {block_num} generation failed: {exc}")
                blocks[block_num] = {
                    "data": None,
                    "sources": [],
                    "confidence": 0.0,
                    "error": str(exc),
                }

        # Собираем паспорт
        passport = Passport(
            id=uuid.uuid4(),
            session_id=uuid.UUID(session_id) if session_id else uuid.uuid4(),
            created_at=datetime.now(timezone.utc),
            block1_general=blocks[1]["data"],
            block1_sources=blocks[1]["sources"],
            block1_confidence=blocks[1]["confidence"],
            block2_sales_model=blocks[2]["data"],
            block2_sources=blocks[2]["sources"],
            block2_confidence=blocks[2]["confidence"],
            block3_pains=blocks[3]["data"],
            block3_sources=blocks[3]["sources"],
            block3_confidence=blocks[3]["confidence"],
            block4_people=blocks[4]["data"],
            block4_sources=blocks[4]["sources"],
            block4_confidence=blocks[4]["confidence"],
            block5_context=blocks[5]["data"],
            block5_sources=blocks[5]["sources"],
            block5_confidence=blocks[5]["confidence"],
            block6_competitors=blocks[6]["data"],
            block6_sources=blocks[6]["sources"],
            block6_confidence=blocks[6]["confidence"],
            block7_readiness=blocks[7]["data"],
            block7_sources=blocks[7]["sources"],
            block7_confidence=blocks[7]["confidence"],
            block8_reputation=blocks[8]["data"],
            block8_sources=blocks[8]["sources"],
            block8_confidence=blocks[8]["confidence"],
            block9_triggers=blocks[9]["data"],
            block9_sources=blocks[9]["sources"],
            block9_confidence=blocks[9]["confidence"],
            block10_lpr=blocks[10]["data"],
            block10_sources=blocks[10]["sources"],
            block10_confidence=blocks[10]["confidence"],
            block11_industry=blocks[11]["data"],
            block11_sources=blocks[11]["sources"],
            block11_confidence=blocks[11]["confidence"],
            top3_hooks=prioritized.top3_hooks,
            raw_collected_data={
                k: v.data for k, v in results.items() if v.is_usable()
            },
        )

        # Сохраняем в БД
        from database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            db.add(passport)
            await db.commit()
            await db.refresh(passport)

        return passport

    async def _generate_block(
        self,
        block_num: int,
        company_name: str,
        results: dict,
        analysis,
        prioritized,
        session_id: Optional[str],
    ) -> dict:
        """Сгенерировать один блок паспорта через Claude Sonnet."""
        block_name, block_fields = BLOCK_PROMPTS[block_num]

        # Подготавливаем данные для блока
        block_data = self._prepare_block_data(block_num, results, analysis, prioritized)
        sources = self._get_block_sources(block_num, results)

        if not block_data:
            return {"data": None, "sources": [], "confidence": 0.0}

        router = self._get_router()
        try:
            result = await router.complete_json(
                task_type=TaskType.PASSPORT_GENERATION,
                prompt=(
                    f"Компания: {company_name}\n"
                    f"Блок паспорта: {block_num}. {block_name}\n"
                    f"Поля для заполнения: {block_fields}\n\n"
                    f"Данные из источников:\n{str(block_data)[:2500]}\n\n"
                    f"Заполни поля блока на русском языке. "
                    f"Факты — с источником в скобках. "
                    f"Гипотезы — помечай '⚠️ Гипотеза: ...'. "
                    f"Нет данных — пиши null или 'Данные не найдены'."
                ),
                max_tokens=800,
                session_id=session_id,
                agent_name=f"passport_block{block_num}",
            )
            confidence = self._calculate_block_confidence(result, sources)
            return {"data": result, "sources": sources, "confidence": confidence}
        except Exception as exc:
            logger.warning(f"Block {block_num} LLM failed: {exc}")
            return {"data": block_data, "sources": sources, "confidence": 0.4}

    def _prepare_block_data(
        self, block_num: int, results: dict, analysis, prioritized
    ) -> dict:
        """Собрать сырые данные для конкретного блока."""
        from agents.analyst import AnalysisResult

        if block_num == 3:
            return {"pains": analysis.pains}
        if block_num == 7:
            return analysis.readiness
        if block_num == 9:
            return analysis.triggers
        if block_num == 10:
            lpr = results.get("linkedin_person")
            if lpr and lpr.is_usable():
                return {**lpr.data, "overheating": analysis.lpr_overheating}
            return {}
        if block_num == 11:
            return analysis.industry_context
        if block_num == 6:
            return {"competitors": analysis.competitors}
        if block_num == 2:
            sales = analysis.sales_model_signals
            website = results.get("website", None)
            return {**sales, **(website.data if website and website.is_usable() else {})}

        # Для остальных блоков — агрегируем из sources
        BLOCK_SOURCES = {
            1: ["website", "linkedin_company", "crunchbase", "similarweb", "twitter"],
            4: ["linkedin_company", "duckduckgo"],
            5: ["duckduckgo", "linkedin_company", "twitter", "youtube"],
            8: ["google_reviews", "trustpilot", "g2", "capterra", "yelp", "glassdoor"],
        }
        sources_for_block = BLOCK_SOURCES.get(block_num, [])
        merged = {}
        for src in sources_for_block:
            r = results.get(src)
            if r and r.is_usable():
                merged[src] = r.data
        return merged

    def _get_block_sources(self, block_num: int, results: dict) -> list[dict]:
        """Список источников с ссылками для блока."""
        BLOCK_SOURCES = {
            1: ["website", "linkedin_company", "crunchbase", "similarweb"],
            2: ["website", "linkedin_company", "indeed", "builtwith"],
            3: ["glassdoor", "g2", "capterra", "trustpilot", "reddit"],
            4: ["linkedin_company", "duckduckgo"],
            5: ["duckduckgo", "linkedin_company", "twitter"],
            6: ["g2", "capterra", "duckduckgo"],
            7: ["crunchbase", "indeed", "builtwith"],
            8: ["google_reviews", "trustpilot", "g2", "glassdoor"],
            9: ["crunchbase", "duckduckgo"],
            10: ["linkedin_person"],
            11: ["duckduckgo", "similarweb"],
        }
        src_names = BLOCK_SOURCES.get(block_num, [])
        return [
            results[s].to_source_ref()
            for s in src_names
            if s in results and results[s].is_usable()
        ]

    def _calculate_block_confidence(self, data: dict, sources: list) -> float:
        if not data:
            return 0.0
        base = 0.5
        if sources:
            base += min(0.4, len(sources) * 0.1)
        return round(min(1.0, base), 2)
