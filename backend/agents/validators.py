"""
ValidatorAgent — проверка качества и достоверности собранных данных.

Алгоритм (раздел 5, Агент 8 ТЗ):
1. Базовая проверка: не пустые, не captcha/login wall
2. Перекрёстная проверка одинаковых полей из разных источников
3. Дата проверка: stale (>6 мес) / outdated (>2 года)
4. Contradiction detection через Gemini Flash
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

from collectors.base import CollectorResult

logger = logging.getLogger(__name__)

LOW_TRUST_SOURCES = {"reddit", "twitter", "yelp"}
STALE_DAYS = 180
OUTDATED_DAYS = 730

# Признаки заглушки (captcha, login wall, 403)
STUB_PATTERNS = [
    "access denied", "403 forbidden", "login to view",
    "sign in to continue", "captcha", "please verify",
    "are you a human", "cloudflare", "enable javascript",
    "just a moment", "checking your browser",
]


@dataclass
class ValidationResult:
    validated_results: list[CollectorResult]
    contradictions: list[dict]       # [{field, source_a, value_a, source_b, value_b}]
    gaps: list[dict]                  # [{collector, reason}]
    cross_validated_facts: dict       # {field: {value: [sources]}}
    staleness_flags: dict             # {source_name: "stale"|"outdated"}


class ValidatorAgent:
    """Валидатор собранных данных."""

    def __init__(self):
        self._router = None

    def _get_router(self):
        if self._router is None:
            from llm.router import get_llm_router
            self._router = get_llm_router()
        return self._router

    async def validate(
        self,
        results: list[CollectorResult],
        session_id: Optional[str] = None,
    ) -> ValidationResult:
        """Валидировать список CollectorResult."""
        validated = []
        gaps = []
        staleness_flags = {}

        for result in results:
            # 1. Базовая проверка
            if not self._is_real_data(result):
                gaps.append({
                    "collector": result.source_name,
                    "reason": "stub_or_empty",
                    "url": result.url_used,
                    "error": result.error_message,
                })
                # Меняем статус на failed
                result.status = "failed"
                result.error_message = result.error_message or "Stub/empty response detected"
                result.confidence = 0.0

            # 2. Дата проверка (если есть retrieved_at)
            age_flag = self._check_staleness(result.retrieved_at)
            if age_flag:
                staleness_flags[result.source_name] = age_flag
                result.confidence *= (0.7 if age_flag == "stale" else 0.4)
                result.confidence = round(result.confidence, 2)

            validated.append(result)

        # 3. Перекрёстная проверка числовых полей
        cross_validated = self._cross_validate(validated)

        # 4. Contradiction detection (LLM — только при явных противоречиях)
        contradictions = await self._detect_contradictions(
            cross_validated, session_id=session_id
        )

        return ValidationResult(
            validated_results=validated,
            contradictions=contradictions,
            gaps=gaps,
            cross_validated_facts=cross_validated,
            staleness_flags=staleness_flags,
        )

    def _is_real_data(self, result: CollectorResult) -> bool:
        """Проверить что данные реальные, не заглушка."""
        if result.status == "not_applicable":
            return True  # not_applicable — не ошибка
        if result.status == "failed":
            return False
        if not result.data:
            return False

        # Проверяем текст на паттерны заглушки
        data_str = str(result.data).lower()
        for pattern in STUB_PATTERNS:
            if pattern in data_str:
                return False

        return True

    def _check_staleness(self, retrieved_at: datetime) -> Optional[str]:
        """Проверить свежесть данных."""
        now = datetime.now(timezone.utc)
        # Убеждаемся что retrieved_at timezone-aware
        if retrieved_at.tzinfo is None:
            retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)
        age_days = (now - retrieved_at).days
        if age_days > OUTDATED_DAYS:
            return "outdated"
        if age_days > STALE_DAYS:
            return "stale"
        return None

    def _cross_validate(
        self, results: list[CollectorResult]
    ) -> dict:
        """
        Перекрёстная проверка — собрать одинаковые поля из разных источников.
        Возвращает {field: {value: [sources]}}
        """
        fields_to_check = [
            "employees_count", "company_size", "rating",
            "founded_year", "industry", "headquarters",
        ]
        cross: dict = {}

        for result in results:
            if not result.is_usable():
                continue
            for field_name in fields_to_check:
                value = result.data.get(field_name)
                if value is None:
                    continue
                val_str = str(value).strip().lower()
                if field_name not in cross:
                    cross[field_name] = {}
                if val_str not in cross[field_name]:
                    cross[field_name][val_str] = []
                cross[field_name][val_str].append(result.source_name)

        return cross

    async def _detect_contradictions(
        self, cross_validated: dict, session_id: Optional[str] = None
    ) -> list[dict]:
        """Обнаружить противоречия через Gemini Flash (только при >1 значении для поля)."""
        contradictions = []

        conflicting = {
            field: values
            for field, values in cross_validated.items()
            if len(values) > 1
        }

        if not conflicting:
            return []

        # Простые случаи решаем детерминированно (по количеству источников)
        unresolved = {}
        for field, values in conflicting.items():
            # Выбираем значение с наибольшим числом источников
            best = max(values.items(), key=lambda x: len(x[1]))
            all_sources = [src for srcs in values.values() for src in srcs]
            if len(best[1]) < len(all_sources) / 2:
                # Реальное противоречие — нет явного большинства
                unresolved[field] = values
            else:
                contradictions.append({
                    "field": field,
                    "resolved_value": best[0],
                    "resolved_by": "majority_vote",
                    "all_values": values,
                })

        # LLM только для сложных случаев (>2 реальных противоречия)
        if len(unresolved) > 1 and session_id:
            try:
                from llm.base import TaskType
                router = self._get_router()
                prompt = (
                    f"These data fields have conflicting values from different sources:\n"
                    f"{unresolved}\n\n"
                    f"For each field, choose the most trustworthy value and explain why.\n"
                    f"Respond in JSON: [{{\"field\": ..., \"chosen_value\": ..., \"reason\": ...}}]"
                )
                result = await router.complete_json(
                    task_type=TaskType.DATA_VALIDATION,
                    prompt=prompt,
                    max_tokens=500,
                    session_id=session_id,
                    agent_name="validators",
                )
                if isinstance(result, list):
                    for item in result:
                        item["resolved_by"] = "llm_gemini"
                        contradictions.append(item)
            except Exception as exc:
                logger.warning(f"LLM contradiction detection failed: {exc}")
                for field, values in unresolved.items():
                    contradictions.append({
                        "field": field,
                        "all_values": values,
                        "resolved_by": "unresolved",
                    })

        return contradictions
