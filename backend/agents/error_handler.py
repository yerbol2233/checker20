"""
ErrorHandlerAgent — обработка пробелов в собранных данных.

Алгоритм (раздел 5, Агент 10 ТЗ):
1. Для каждого gap: ищем альтернативный источник
2. Если найден — запускаем синхронно
3. Если нет — фиксируем причину: source_unavailable | no_data_found | access_denied | timeout
4. Обязательные блоки без данных → passport_status = not_ready
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

from agents.validators import ValidationResult
from collectors.base import CollectorResult

logger = logging.getLogger(__name__)

# Обязательные блоки паспорта
MANDATORY_BLOCKS = [1, 2, 4]

# Альтернативные источники для каждого коллектора
ALTERNATIVE_SOURCES: dict[str, list[str]] = {
    "glassdoor": ["indeed", "reddit"],
    "linkedin_company": ["duckduckgo", "website"],
    "crunchbase": ["duckduckgo", "sec_edgar"],
    "g2": ["capterra", "trustpilot"],
    "similarweb": ["duckduckgo"],
    "indeed": ["glassdoor", "duckduckgo"],
}

# Маппинг блоков → обязательные коллекторы
BLOCK_REQUIRED_COLLECTORS: dict[int, list[str]] = {
    1: ["website", "linkedin_company"],
    2: ["website", "linkedin_company"],
    4: ["linkedin_company", "duckduckgo"],
}


@dataclass
class CleanedData:
    results_by_source: dict[str, CollectorResult]  # source_name → result
    gaps: list[dict]                                # финальные необработанные gaps
    is_passport_ready: bool = True
    not_ready_reasons: list[dict] = field(default_factory=list)
    retry_results: list[CollectorResult] = field(default_factory=list)


class ErrorHandlerAgent:
    """Обработчик ошибок и пробелов в данных."""

    async def process(
        self,
        validation_result: ValidationResult,
        context: dict,
        session_id: Optional[str] = None,
    ) -> CleanedData:
        """Обработать результаты валидации, заполнить пробелы где возможно."""

        # Строим карту результатов
        results_map: dict[str, CollectorResult] = {
            r.source_name: r for r in validation_result.validated_results
        }

        final_gaps = list(validation_result.gaps)
        retry_results: list[CollectorResult] = []

        # Пробуем заполнить gaps альтернативными источниками
        failed_sources = {
            g["collector"] for g in validation_result.gaps
            if g.get("reason") not in ("not_applicable",)
        }

        for failed_source in failed_sources:
            alternatives = ALTERNATIVE_SOURCES.get(failed_source, [])
            for alt_name in alternatives:
                # Пропускаем если альтернатива уже успешна
                existing = results_map.get(alt_name)
                if existing and existing.is_usable():
                    continue
                # Запускаем альтернативный коллектор
                try:
                    alt_result = await self._run_collector(alt_name, context)
                    if alt_result and alt_result.is_usable():
                        results_map[alt_name] = alt_result
                        retry_results.append(alt_result)
                        logger.info(
                            f"Alternative {alt_name} succeeded for failed {failed_source}"
                        )
                        break
                except Exception as exc:
                    logger.debug(f"Alternative {alt_name} also failed: {exc}")

        # Классифицируем финальные gaps по причинам
        final_gaps_classified = []
        for gap in final_gaps:
            source = gap.get("collector", "")
            error = (gap.get("error") or "").lower()
            if "403" in error or "access denied" in error or "denied" in error:
                reason = "access_denied"
            elif "timeout" in error:
                reason = "timeout"
            elif "not found" in error or "no results" in error:
                reason = "no_data_found"
            else:
                reason = "source_unavailable"
            final_gaps_classified.append({**gap, "classified_reason": reason})

        # Проверяем обязательные блоки
        is_ready = True
        not_ready_reasons = []

        for block_num, required_collectors in BLOCK_REQUIRED_COLLECTORS.items():
            block_has_data = any(
                results_map.get(c) and results_map[c].is_usable()
                for c in required_collectors
            )
            if not block_has_data:
                is_ready = False
                not_ready_reasons.append({
                    "block_id": block_num,
                    "reason": f"Блок {block_num} — нет данных от {required_collectors}",
                })

        return CleanedData(
            results_by_source=results_map,
            gaps=final_gaps_classified,
            is_passport_ready=is_ready,
            not_ready_reasons=not_ready_reasons,
            retry_results=retry_results,
        )

    async def _run_collector(self, collector_name: str, context: dict) -> Optional[CollectorResult]:
        """Запустить коллектор по имени."""
        from collectors import (
            WebsiteCollector, DuckDuckGoCollector, LinkedInCompanyCollector,
            IndeedCollector, GlassdoorCollector, CrunchbaseCollector,
            TrustpilotCollector, CapterraCollector, RedditCollector,
            SimilarWebCollector,
        )
        collector_map = {
            "website": WebsiteCollector,
            "duckduckgo": DuckDuckGoCollector,
            "linkedin_company": LinkedInCompanyCollector,
            "indeed": IndeedCollector,
            "glassdoor": GlassdoorCollector,
            "crunchbase": CrunchbaseCollector,
            "trustpilot": TrustpilotCollector,
            "capterra": CapterraCollector,
            "reddit": RedditCollector,
            "similarweb": SimilarWebCollector,
        }
        cls = collector_map.get(collector_name)
        if not cls:
            return None
        collector = cls()
        return await collector.safe_collect(context)
