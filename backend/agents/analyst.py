"""
AnalystAgent — главный LLM-агент анализа компании.

Задачи (раздел 5, Агент 3 ТЗ):
1. Анализ болей (Блок 3) → Claude Opus
2. Оценка готовности к покупке (Блок 7) → детерминированный scoring + Claude
3. Оценка перегретости ЛПР (Блок 10) → детерминированный + Gemini
4. Триггеры входа (Блок 9) → Claude Opus агрегация

Правила: никогда не выдумывать данные. Нет данных = нет вывода.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from agents.error_handler import CleanedData
from llm.base import TaskType

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    pains: list[dict]             # Блок 3
    readiness: dict               # Блок 7
    lpr_overheating: dict         # Блок 10 (если есть ЛПР)
    triggers: dict                # Блок 9
    industry_context: dict        # Блок 11
    sales_model_signals: dict     # Блок 2
    competitors: list[dict]       # Блок 6
    raw_analysis: dict = field(default_factory=dict)


class AnalystAgent:
    """Аналитик — извлекает выводы из очищенных данных через LLM."""

    def __init__(self):
        self._router = None
        self._product_config = None

    def _get_router(self):
        if self._router is None:
            from llm.router import get_llm_router
            self._router = get_llm_router()
        return self._router

    def _get_product_context(self) -> str:
        if self._product_config is None:
            from agents.product_config import ProductConfiguratorAgent
            self._product_config = ProductConfiguratorAgent()
        return self._product_config.format_for_llm()

    async def analyze(
        self,
        cleaned_data: CleanedData,
        context: dict,
        session_id: Optional[str] = None,
    ) -> AnalysisResult:
        """Выполнить полный анализ компании."""
        results = cleaned_data.results_by_source
        company_name = context.get("company_name", "Unknown")
        has_lpr = bool(context.get("linkedin_lpr_url"))

        # Собираем данные по блокам
        block_data = self._aggregate_by_block(results)

        # Параллельно запускаем анализ
        import asyncio
        pains_task = asyncio.create_task(
            self._analyze_pains(block_data, company_name, session_id)
        )
        readiness_task = asyncio.create_task(
            self._calculate_readiness(block_data, results)
        )
        triggers_task = asyncio.create_task(
            self._extract_triggers(block_data, company_name, session_id)
        )
        competitors_task = asyncio.create_task(
            self._extract_competitors(block_data, company_name, session_id)
        )
        industry_task = asyncio.create_task(
            self._analyze_industry(block_data, company_name, session_id)
        )
        sales_model_task = asyncio.create_task(
            self._analyze_sales_model(block_data, company_name, session_id)
        )

        pains = await pains_task
        readiness = await readiness_task
        triggers = await triggers_task
        competitors = await competitors_task
        industry_context = await industry_task
        sales_model_signals = await sales_model_task

        # ЛПР анализ (только если есть данные)
        lpr_overheating = {}
        if has_lpr and results.get("linkedin_person"):
            lpr_data = results["linkedin_person"].data
            lpr_overheating = await self._calculate_lpr_overheating(
                lpr_data, session_id
            )

        return AnalysisResult(
            pains=pains,
            readiness=readiness,
            lpr_overheating=lpr_overheating,
            triggers=triggers,
            industry_context=industry_context,
            sales_model_signals=sales_model_signals,
            competitors=competitors,
        )

    def _aggregate_by_block(self, results: dict) -> dict:
        """Агрегировать данные по блокам паспорта (маппинг из раздела 6.1 ТЗ)."""
        usable = {k: v.data for k, v in results.items() if v.is_usable()}

        def merge(*source_names: str) -> dict:
            merged = {}
            for name in source_names:
                d = usable.get(name, {})
                merged.update({f"{name}__{k}": v for k, v in d.items()})
            return merged

        return {
            "block1": merge("website", "linkedin_company", "crunchbase", "similarweb", "twitter", "youtube"),
            "block2": merge("website", "linkedin_company", "indeed", "builtwith", "glassdoor", "duckduckgo"),
            "block3": merge("glassdoor", "g2", "capterra", "trustpilot", "yelp", "reddit", "indeed", "duckduckgo"),
            "block4": merge("linkedin_company", "duckduckgo", "linkedin_person"),
            "block5": merge("duckduckgo", "linkedin_company", "twitter", "youtube"),
            "block6": merge("g2", "capterra", "duckduckgo", "crunchbase"),
            "block7": merge("website", "linkedin_company", "indeed", "builtwith", "duckduckgo"),
            "block8": merge("google_reviews", "trustpilot", "g2", "capterra", "yelp", "glassdoor"),
            "block9": merge("crunchbase", "linkedin_company", "duckduckgo"),
            "block10": merge("linkedin_person", "twitter", "duckduckgo"),
            "block11": merge("duckduckgo", "g2", "similarweb"),
        }

    async def _analyze_pains(
        self, block_data: dict, company_name: str, session_id: Optional[str]
    ) -> list[dict]:
        """Анализ болей (Блок 3) через Claude Opus."""
        b3_data = block_data.get("block3", {})
        b2_data = block_data.get("block2", {})

        if not b3_data and not b2_data:
            return []

        product_ctx = self._get_product_context()
        prompt = (
            f"Company: {company_name}\n\n"
            f"Collected data about company problems and employee/customer feedback:\n"
            f"{str({**b3_data, **b2_data})[:3000]}\n\n"
            f"Our product context:\n{product_ctx}\n\n"
            f"Identify ONLY fact-backed hypotheses about sales process pains.\n"
            f"Rules:\n"
            f"1. Each pain = FACT → HYPOTHESIS (no templates)\n"
            f"2. Priority: pains related to sales and conversion funnel\n"
            f"3. Confidence 0.0-1.0 for each\n"
            f"4. No fabrication. No data = no pain\n"
            f"5. Mark hypothesis: true if inferred from indirect signals\n\n"
            f"Respond in JSON array: "
            f'[{{"pain": "...", "fact": "...", "hypothesis": true/false, '
            f'"confidence": 0.8, "source_blocks": [3, 8]}}]'
        )

        router = self._get_router()
        try:
            result = await router.complete_json(
                task_type=TaskType.PAIN_ANALYSIS,
                prompt=prompt,
                max_tokens=1500,
                session_id=session_id,
                agent_name="analyst_pains",
            )
            if isinstance(result, list):
                return result
        except Exception as exc:
            logger.warning(f"Pain analysis failed: {exc}")
        return []

    async def _calculate_readiness(
        self, block_data: dict, results: dict
    ) -> dict:
        """Детерминированный scoring готовности к покупке (Блок 7)."""
        score = 0
        factors = []

        # Финансовая возможность
        crunchbase_data = results.get("crunchbase")
        if crunchbase_data and crunchbase_data.is_usable():
            last_round = crunchbase_data.data.get("last_round_type", "")
            if last_round in ["Series A", "Series B", "Series C", "Public", "IPO"]:
                score += 25
                factors.append("Финансирование Series A+")
            elif last_round in ["Seed", "Pre-Seed"]:
                score += 10
                factors.append("Seed финансирование")

        # Наличие отдела продаж
        indeed_data = results.get("indeed")
        if indeed_data and indeed_data.is_usable():
            jobs_count = indeed_data.data.get("open_jobs_count", 0)
            if jobs_count and int(str(jobs_count).replace(",", "")) > 3:
                score += 20
                factors.append(f"Активный найм ({jobs_count} вакансий)")
            elif jobs_count:
                score += 10

        # Технологическая зрелость (CRM)
        builtwith_data = results.get("builtwith")
        if builtwith_data and builtwith_data.is_usable():
            sales_tech = builtwith_data.data.get("sales_tech_detected", [])
            if sales_tech:
                score += 10
                factors.append(f"Sales tech: {', '.join(sales_tech[:3])}")

        # Трафик (SimilarWeb — свидетельство масштаба)
        sw_data = results.get("similarweb")
        if sw_data and sw_data.is_usable():
            visits = sw_data.data.get("monthly_visits", "")
            if visits and any(c in str(visits) for c in ["K", "M", "k", "m"]):
                score += 10
                factors.append(f"Трафик: {visits} визитов/мес")

        score = min(100, score)
        level = "высокая" if score >= 60 else "средняя" if score >= 30 else "низкая"

        return {
            "score": score,
            "level": level,
            "factors": factors,
            "verdict": f"Готовность к покупке: {level} ({score}/100)",
        }

    async def _calculate_lpr_overheating(
        self, lpr_data: dict, session_id: Optional[str]
    ) -> dict:
        """Scoring перегретости ЛПР."""
        score = 0
        signals = []

        posts_per_month = lpr_data.get("posts_per_month_estimate", 0)
        connections = lpr_data.get("connections", 0)
        followers = lpr_data.get("followers", 0)
        profile_type = lpr_data.get("profile_type", "quiet_pro")

        if posts_per_month >= 8:
            score += 20
            signals.append("Высокая активность в LinkedIn (8+ постов/мес)")
        elif posts_per_month >= 3:
            score += 10
            signals.append("Умеренная активность в LinkedIn")

        if connections > 5000:
            score += 10
            signals.append("5000+ связей — активный нетворкер")

        if profile_type == "creator":
            score += 15
            signals.append("Тип профиля: создатель контента")

        level = "перегрет" if score >= 60 else "нормальный" if score >= 30 else "доступный"

        # LLM оценка если есть посты
        recent_posts = lpr_data.get("recent_posts", [])
        llm_assessment = ""
        if recent_posts and session_id:
            try:
                router = self._get_router()
                posts_text = "\n".join(p.get("text", "") for p in recent_posts[:3])
                resp = await router.complete(
                    task_type=TaskType.LPR_SCORING,
                    prompt=(
                        f"LinkedIn profile type: {profile_type}\n"
                        f"Recent posts:\n{posts_text}\n\n"
                        f"Assess in 1-2 sentences: how receptive is this person to cold outreach? "
                        f"What's the best angle to use?"
                    ),
                    max_tokens=150,
                    temperature=0.5,
                    session_id=session_id,
                    agent_name="analyst_lpr",
                )
                llm_assessment = resp.content.strip()
            except Exception as exc:
                logger.debug(f"LPR LLM scoring failed: {exc}")

        return {
            "score": score,
            "level": level,
            "signals": signals,
            "lpr_assessment": llm_assessment,
            "profile_type": profile_type,
        }

    async def _extract_triggers(
        self, block_data: dict, company_name: str, session_id: Optional[str]
    ) -> dict:
        """Агрегация триггеров входа (Блок 9)."""
        trigger_data = {**block_data.get("block1", {}), **block_data.get("block9", {})}
        if not trigger_data:
            return {"positive": [], "negative": [], "verdict": "Триггеры не обнаружены"}

        router = self._get_router()
        try:
            result = await router.complete_json(
                task_type=TaskType.PAIN_ANALYSIS,
                prompt=(
                    f"Company: {company_name}\n"
                    f"Data: {str(trigger_data)[:2000]}\n\n"
                    f"Identify entry triggers (signals that NOW is a good time to reach out).\n"
                    f'JSON: {{"positive": [{{"trigger": "...", "source": "...", "strength": "high/medium/low"}}], '
                    f'"negative": [...], "verdict": "..."}}'
                ),
                max_tokens=600,
                session_id=session_id,
                agent_name="analyst_triggers",
            )
            if isinstance(result, dict):
                return result
        except Exception as exc:
            logger.warning(f"Triggers extraction failed: {exc}")
        return {"positive": [], "negative": [], "verdict": "Анализ триггеров недоступен"}

    async def _extract_competitors(
        self, block_data: dict, company_name: str, session_id: Optional[str]
    ) -> list[dict]:
        """Конкурентная среда (Блок 6)."""
        comp_data = block_data.get("block6", {})
        if not comp_data:
            return []

        router = self._get_router()
        try:
            result = await router.complete_json(
                task_type=TaskType.DATA_VALIDATION,
                prompt=(
                    f"Company: {company_name}\n"
                    f"Data: {str(comp_data)[:1500]}\n\n"
                    f"Extract competitors mentioned. "
                    f'JSON array: [{{"name": "...", "source": "...", "relationship": "direct/indirect"}}]'
                ),
                max_tokens=400,
                session_id=session_id,
                agent_name="analyst_competitors",
            )
            if isinstance(result, list):
                return result
        except Exception as exc:
            logger.debug(f"Competitors extraction failed: {exc}")
        return []

    async def _analyze_industry(
        self, block_data: dict, company_name: str, session_id: Optional[str]
    ) -> dict:
        """Контекст отрасли (Блок 11)."""
        ind_data = block_data.get("block11", {})
        if not ind_data:
            return {"trends": [], "summary": "Данные не найдены"}

        router = self._get_router()
        try:
            result = await router.complete_json(
                task_type=TaskType.NICHE_CLASSIFICATION,
                prompt=(
                    f"Company: {company_name}\n"
                    f"Data: {str(ind_data)[:1500]}\n\n"
                    f"Summarize industry context relevant for B2B sales outreach. "
                    f'JSON: {{"industry": "...", "trends": ["..."], "summary": "...", "market_size": "..."}}'
                ),
                max_tokens=400,
                session_id=session_id,
                agent_name="analyst_industry",
            )
            return result if isinstance(result, dict) else {"summary": "Данные не найдены"}
        except Exception as exc:
            logger.debug(f"Industry analysis failed: {exc}")
        return {"trends": [], "summary": "Данные не найдены"}

    async def _analyze_sales_model(
        self, block_data: dict, company_name: str, session_id: Optional[str]
    ) -> dict:
        """Сигналы модели продаж (Блок 2)."""
        b2_data = block_data.get("block2", {})
        if not b2_data:
            return {}

        router = self._get_router()
        try:
            result = await router.complete_json(
                task_type=TaskType.DATA_VALIDATION,
                prompt=(
                    f"Company: {company_name}\n"
                    f"Data: {str(b2_data)[:2000]}\n\n"
                    f"Extract sales model signals. "
                    f'JSON: {{"has_sales_team": true/false, "sales_channels": ["..."], '
                    f'"has_crm": true/false, "uses_phone_sales": true/false, '
                    f'"estimated_team_size": "...", "sales_tools": ["..."]}}'
                ),
                max_tokens=400,
                session_id=session_id,
                agent_name="analyst_sales_model",
            )
            return result if isinstance(result, dict) else {}
        except Exception as exc:
            logger.debug(f"Sales model analysis failed: {exc}")
        return {}
