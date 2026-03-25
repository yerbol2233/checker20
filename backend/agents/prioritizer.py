"""
PrioritizerAgent — приоритизация блоков, топ-3 зацепки, шкала полноты.

Раздел 5, Агент 9 ТЗ.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from agents.analyst import AnalysisResult
from agents.error_handler import CleanedData
from llm.base import TaskType

logger = logging.getLogger(__name__)

BLOCK_NAMES = {
    1: "Общий профиль",
    2: "Модель продаж",
    3: "Потенциальные боли",
    4: "Ключевые люди",
    5: "Контекст и зацепки",
    6: "Конкурентная среда",
    7: "Готовность к покупке",
    8: "Репутация и отзывы",
    9: "Триггеры входа",
    10: "Профиль ЛПР",
    11: "Контекст отрасли",
}

# Веса блоков
MANDATORY_BLOCKS = [1, 2, 4]
DESIRABLE_BLOCKS = [3, 5, 6, 8, 9, 11]
BONUS_BLOCKS = [7]


@dataclass
class CompletenessResult:
    score: int          # 0-100
    is_ready: bool
    reasons: list[dict] = field(default_factory=list)  # [{block_id, reason}]


@dataclass
class PrioritizedData:
    blocks_filled: dict[int, bool]
    top3_hooks: list[dict]
    completeness: CompletenessResult
    analysis: AnalysisResult
    cleaned_data: CleanedData


class PrioritizerAgent:
    """Приоритизатор — вычисляет полноту и ранжирует зацепки."""

    def __init__(self):
        self._router = None

    def _get_router(self):
        if self._router is None:
            from llm.router import get_llm_router
            self._router = get_llm_router()
        return self._router

    async def prioritize(
        self,
        cleaned_data: CleanedData,
        analysis: AnalysisResult,
        context: dict,
        session_id: Optional[str] = None,
    ) -> PrioritizedData:
        """Вычислить приоритеты, полноту и топ-3 зацепки."""
        lpr_provided = bool(context.get("linkedin_lpr_url"))

        blocks_filled = self._assess_blocks_filled(cleaned_data, analysis)
        completeness = self._calculate_completeness(blocks_filled, lpr_provided)
        top3_hooks = await self._compute_top3_hooks(
            analysis, cleaned_data, context, session_id
        )

        return PrioritizedData(
            blocks_filled=blocks_filled,
            top3_hooks=top3_hooks,
            completeness=completeness,
            analysis=analysis,
            cleaned_data=cleaned_data,
        )

    def _assess_blocks_filled(
        self, cleaned_data: CleanedData, analysis: AnalysisResult
    ) -> dict[int, bool]:
        results = cleaned_data.results_by_source

        def has(*sources: str) -> bool:
            return any(results.get(s) and results[s].is_usable() for s in sources)

        return {
            1: has("website", "linkedin_company", "crunchbase"),
            2: has("website", "linkedin_company", "indeed"),
            3: bool(analysis.pains),
            4: has("linkedin_company", "duckduckgo"),
            5: has("duckduckgo", "linkedin_company", "twitter"),
            6: bool(analysis.competitors),
            7: bool(analysis.readiness.get("score", 0)),
            8: has("google_reviews", "trustpilot", "g2", "capterra", "yelp", "glassdoor"),
            9: bool(analysis.triggers.get("positive")),
            10: has("linkedin_person") and bool(analysis.lpr_overheating),
            11: bool(analysis.industry_context.get("summary", "") != "Данные не найдены"),
        }

    def _calculate_completeness(
        self, blocks_filled: dict[int, bool], lpr_provided: bool
    ) -> CompletenessResult:
        """Вычислить шкалу полноты (раздел 5, Агент 9 ТЗ)."""
        mandatory = list(MANDATORY_BLOCKS)
        if lpr_provided:
            mandatory.append(10)

        filled_mandatory = sum(1 for b in mandatory if blocks_filled.get(b))
        filled_desirable = sum(1 for b in DESIRABLE_BLOCKS if blocks_filled.get(b))

        score = (
            (filled_mandatory / len(mandatory)) * 70
            + (filled_desirable / len(DESIRABLE_BLOCKS)) * 30
        )

        is_ready = (
            filled_mandatory == len(mandatory) and filled_desirable >= 3
        )

        reasons = []
        for b in mandatory:
            if not blocks_filled.get(b):
                reasons.append({
                    "block_id": b,
                    "reason": f"Блок {b} ({BLOCK_NAMES[b]}) не заполнен",
                })

        return CompletenessResult(
            score=round(score),
            is_ready=is_ready,
            reasons=reasons,
        )

    async def _compute_top3_hooks(
        self,
        analysis: AnalysisResult,
        cleaned_data: CleanedData,
        context: dict,
        session_id: Optional[str],
    ) -> list[dict]:
        """Вычислить топ-3 зацепки по матрице freshness × emotional_strength × uniqueness."""
        candidates = []

        # Из Блока 10 (ЛПР посты)
        lpr_result = cleaned_data.results_by_source.get("linkedin_person")
        if lpr_result and lpr_result.is_usable():
            posts = lpr_result.data.get("recent_posts", [])
            for post in posts[:3]:
                candidates.append({
                    "hook": post.get("text", "")[:150],
                    "source": "linkedin_person",
                    "source_block": 10,
                    "freshness_days": 7,  # предполагаем свежее
                })

        # Из Блока 5 (новости, посты компании)
        ddg_result = cleaned_data.results_by_source.get("duckduckgo")
        if ddg_result and ddg_result.is_usable():
            news = ddg_result.data.get("results", {}).get("news", [])
            for item in news[:3]:
                candidates.append({
                    "hook": item.get("title", ""),
                    "source": "duckduckgo",
                    "source_block": 5,
                    "freshness_days": 30,
                })

        # Из Блока 9 (триггеры)
        for trigger in analysis.triggers.get("positive", [])[:3]:
            candidates.append({
                "hook": trigger.get("trigger", ""),
                "source": trigger.get("source", ""),
                "source_block": 9,
                "freshness_days": 14,
            })

        if not candidates:
            return []

        # Оцениваем через Gemini Flash
        try:
            router = self._get_router()
            company = context.get("company_name", "")
            result = await router.complete_json(
                task_type=TaskType.HOOK_PRIORITIZATION,
                prompt=(
                    f"Company: {company}\n"
                    f"Candidate hooks for B2B outreach:\n"
                    f"{candidates}\n\n"
                    f"Score each hook (0.0-1.0) for: emotional_strength, uniqueness.\n"
                    f"Formula: score = freshness_score(days)*0.4 + emotional*0.35 + uniqueness*0.25\n"
                    f"freshness: 1.0 if <7d, 0.7 if <30d, 0.3 if <90d\n"
                    f"Return top 3 sorted by score.\n"
                    f'JSON: [{{"rank": 1, "hook": "...", "source_block": 10, '
                    f'"freshness_days": 5, "emotional_strength": 0.9, '
                    f'"uniqueness": 0.8, "score": 0.87, "rationale": "..."}}]'
                ),
                max_tokens=600,
                session_id=session_id,
                agent_name="prioritizer",
            )
            if isinstance(result, list):
                return result[:3]
        except Exception as exc:
            logger.warning(f"Hook prioritization LLM failed: {exc}")

        # Fallback: вернуть первые 3 без scoring
        return [
            {
                "rank": i + 1,
                "hook": c["hook"],
                "source_block": c.get("source_block"),
                "freshness_days": c.get("freshness_days", 30),
                "score": 0.5,
                "rationale": "Scored without LLM",
            }
            for i, c in enumerate(candidates[:3])
        ]
