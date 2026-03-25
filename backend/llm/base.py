"""
LLMProvider — абстрактный базовый класс + общие dataclass'ы.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── TaskType ────────────────────────────────────────────────────────────────

class TaskType(str, Enum):
    # Задачи Claude Opus (глубокое рассуждение)
    PAIN_ANALYSIS = "pain_analysis"
    LPR_ANALYSIS = "lpr_analysis"
    OUTREACH_GENERATION = "outreach_generation"

    # Задачи Claude Sonnet (баланс качество/скорость)
    PASSPORT_GENERATION = "passport_generation"

    # Задачи Gemini Flash (скорость + дешевизна)
    DATA_VALIDATION = "data_validation"
    NICHE_CLASSIFICATION = "niche_classification"
    LPR_SCORING = "lpr_scoring"
    HOOK_PRIORITIZATION = "hook_prioritization"

    # Общие
    GENERAL = "general"


# Маппинг задачи → предпочтительный провайдер
TASK_TO_PROVIDER: dict[TaskType, str] = {
    TaskType.PAIN_ANALYSIS: "claude",
    TaskType.LPR_ANALYSIS: "claude",
    TaskType.OUTREACH_GENERATION: "claude",
    TaskType.PASSPORT_GENERATION: "claude",
    TaskType.DATA_VALIDATION: "gemini",
    TaskType.NICHE_CLASSIFICATION: "gemini",
    TaskType.LPR_SCORING: "gemini",
    TaskType.HOOK_PRIORITIZATION: "gemini",
    TaskType.GENERAL: "claude",
}

# Модели по провайдеру и задаче
TASK_TO_MODEL: dict[TaskType, str] = {
    TaskType.PAIN_ANALYSIS: "claude-opus-4-5",
    TaskType.LPR_ANALYSIS: "claude-opus-4-5",
    TaskType.OUTREACH_GENERATION: "claude-opus-4-5",
    TaskType.PASSPORT_GENERATION: "claude-sonnet-4-5",
    TaskType.DATA_VALIDATION: "gemini-2.5-flash",
    TaskType.NICHE_CLASSIFICATION: "gemini-2.5-flash",
    TaskType.LPR_SCORING: "gemini-2.5-flash",
    TaskType.HOOK_PRIORITIZATION: "gemini-2.5-flash",
    TaskType.GENERAL: "claude-sonnet-4-5",
}

# Стоимость токенов (USD per 1K токенов) — раздел 8.3 ТЗ
TOKEN_COSTS_USD: dict[str, dict[str, float]] = {
    "claude-opus-4-5": {"input": 0.015, "output": 0.075},
    "claude-sonnet-4-5": {"input": 0.003, "output": 0.015},
    "gemini-2.5-flash": {"input": 0.000075, "output": 0.0003},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
}


# ── LLMUsage / LLMResponse ───────────────────────────────────────────────────

@dataclass
class LLMUsage:
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    usage: LLMUsage
    task_type: TaskType
    cost_usd: float = 0.0
    raw_response: Optional[object] = field(default=None, repr=False)

    @classmethod
    def calculate_cost(cls, model: str, usage: LLMUsage) -> float:
        costs = TOKEN_COSTS_USD.get(model, {"input": 0.0, "output": 0.0})
        return (
            (usage.prompt_tokens / 1000) * costs["input"]
            + (usage.completion_tokens / 1000) * costs["output"]
        )


# ── LLMProvider ABC ──────────────────────────────────────────────────────────

class LLMProvider(ABC):
    """
    Абстрактный базовый класс для всех LLM провайдеров.
    Каждый провайдер реализует complete() и возвращает LLMResponse.
    """

    provider_name: str = "base"
    default_model: str = ""

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        task_type: TaskType = TaskType.GENERAL,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """
        Выполнить LLM-запрос.

        Args:
            prompt: основной промпт (user message)
            system_prompt: системный промпт (контекст)
            max_tokens: максимум токенов в ответе
            temperature: температура генерации
            task_type: тип задачи (для выбора модели и логирования)
            model: явное указание модели (переопределяет default)

        Returns:
            LLMResponse с контентом и метриками
        """
        ...

    def is_available(self) -> bool:
        """Проверить, настроен ли провайдер (есть ли API ключ)."""
        return True


# ── Exceptions ───────────────────────────────────────────────────────────────

class LLMProviderError(Exception):
    """Ошибка провайдера (rate limit, API error, etc.)."""
    pass


class AllProvidersFailedError(Exception):
    """Все провайдеры недоступны."""
    pass
