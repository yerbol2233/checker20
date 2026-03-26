"""
LLMRouter — маршрутизатор запросов к LLM провайдерам.

Логика:
1. Определяет приоритетный провайдер по TaskType (раздел 8.1 ТЗ)
2. При ошибке провайдера — переключается на следующий в цепочке fallback
3. Логирует токены через TokenTracker
4. Поддерживает JSON-режим (structured output)

Цепочка fallback: claude → gemini → openai
"""
import json
import logging
import re
from typing import Optional
from json_repair import repair_json

from llm.base import (
    LLMProvider, LLMResponse, LLMUsage, TaskType,
    TASK_TO_PROVIDER, LLMProviderError, AllProvidersFailedError,
)
from llm.claude_client import ClaudeClient
from llm.gemini_client import GeminiClient
from llm.openai_client import OpenAIClient
from llm.token_tracker import get_token_tracker

logger = logging.getLogger(__name__)

FALLBACK_CHAIN = ["claude", "gemini", "openai"]


class LLMRouter:
    """
    Маршрутизатор LLM-запросов с автоматическим fallback.

    Использование:
        router = LLMRouter()
        response = await router.complete(
            task_type=TaskType.PAIN_ANALYSIS,
            prompt="...",
            system_prompt="...",
            session_id="uuid",
            agent_name="analyst",
        )
    """

    def __init__(
        self,
        claude: Optional[ClaudeClient] = None,
        gemini: Optional[GeminiClient] = None,
        openai: Optional[OpenAIClient] = None,
    ):
        self.providers: dict[str, LLMProvider] = {
            "claude": claude or ClaudeClient(),
            "gemini": gemini or GeminiClient(),
            "openai": openai or OpenAIClient(),
        }
        self._token_tracker = get_token_tracker()

    async def complete(
        self,
        task_type: TaskType,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        session_id: Optional[str] = None,
        agent_name: str = "unknown",
        model: Optional[str] = None,
    ) -> LLMResponse:
        """
        Выполнить LLM-запрос с автоматическим выбором провайдера и fallback.

        Args:
            task_type: тип задачи (определяет провайдер и модель)
            prompt: промпт пользователя
            system_prompt: системный промпт
            max_tokens: максимум токенов
            temperature: температура
            session_id: ID сессии (для трекинга токенов)
            agent_name: имя агента (для логов)
            model: явное указание модели (переопределяет роутинг)

        Returns:
            LLMResponse с контентом и метриками

        Raises:
            AllProvidersFailedError: если все провайдеры недоступны
        """
        primary = TASK_TO_PROVIDER.get(task_type, "claude")
        order = [primary] + [p for p in FALLBACK_CHAIN if p != primary]

        last_error: Optional[Exception] = None

        for provider_name in order:
            provider = self.providers.get(provider_name)
            if not provider or not provider.is_available():
                logger.debug(f"Provider {provider_name} not available, skipping")
                continue

            try:
                logger.debug(
                    f"[{agent_name}] task={task_type.value} → provider={provider_name}"
                )
                response = await provider.complete(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    task_type=task_type,
                    model=model,
                )

                # Трекинг токенов
                if session_id:
                    await self._token_tracker.log(
                        session_id=session_id,
                        agent_name=agent_name,
                        llm_provider=provider_name,
                        model_name=response.model,
                        usage=response.usage,
                        cost_usd=response.cost_usd,
                        task_type=task_type,
                        task_description=f"{agent_name}:{task_type.value}",
                    )

                return response

            except LLMProviderError as exc:
                logger.warning(
                    f"Provider {provider_name} failed for task {task_type.value}: {exc}"
                    + (f", trying next" if provider_name != order[-1] else "")
                )
                last_error = exc
                continue

        raise AllProvidersFailedError(
            f"All LLM providers failed for task {task_type.value}. "
            f"Last error: {last_error}"
        )

    async def complete_json(
        self,
        task_type: TaskType,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2000,
        session_id: Optional[str] = None,
        agent_name: str = "unknown",
    ) -> dict:
        """
        Выполнить запрос и распарсить JSON из ответа.
        Добавляет инструкцию о JSON в system_prompt.

        Returns:
            dict с распарсенным JSON или {"raw": content} при ошибке парсинга
        """
        json_instruction = (
            "\n\nIMPORTANT: Respond ONLY with valid JSON. "
            "No explanations, no markdown code blocks, just pure JSON."
        )
        full_system = (system_prompt or "") + json_instruction

        response = await self.complete(
            task_type=task_type,
            prompt=prompt,
            system_prompt=full_system,
            max_tokens=max_tokens,
            temperature=0.3,  # Ниже для детерминизма JSON
            session_id=session_id,
            agent_name=agent_name,
        )

        content = response.content.strip()

        # Убираем markdown-обёртку если есть
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)

        try:
            # Сначала пробуем обычный json
            return json.loads(content)
        except json.JSONDecodeError:
            # Если не вышло — пробуем json_repair
            try:
                repaired = repair_json(content)
                return json.loads(repaired)
            except Exception as exc:
                logger.warning(f"JSON repair failed for {agent_name}: {exc}. Raw: {content[:200]}")
                # Последний шанс: поиск JSON через regex
                json_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", content)
                if json_match:
                    try:
                        return json.loads(repair_json(json_match.group(1)))
                    except Exception:
                        pass
                return {"raw": content, "parse_error": str(exc)}


# Фабрика синглтона
_router_instance: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = LLMRouter()
    return _router_instance
