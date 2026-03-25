"""
ClaudeClient — Anthropic Claude провайдер.

Модели:
- claude-opus-4-5  → глубокий анализ (боли, ЛПР, outreach)
- claude-sonnet-4-5 → сборка паспорта (баланс качество/скорость)
"""
import logging
from typing import Optional

from llm.base import (
    LLMProvider, LLMResponse, LLMUsage, TaskType,
    TASK_TO_MODEL, TOKEN_COSTS_USD, LLMProviderError,
)
from config import settings

logger = logging.getLogger(__name__)


class ClaudeClient(LLMProvider):
    provider_name = "claude"
    default_model = "claude-sonnet-4-5"

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or settings.anthropic_api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        task_type: TaskType = TaskType.GENERAL,
        model: Optional[str] = None,
    ) -> LLMResponse:
        if not self.is_available():
            raise LLMProviderError("Anthropic API key not configured")

        selected_model = model or TASK_TO_MODEL.get(task_type, self.default_model)

        messages = [{"role": "user", "content": prompt}]
        kwargs: dict = {
            "model": selected_model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        # Claude поддерживает температуру только для не-thinking моделей
        # Добавляем только если не Opus с extended thinking
        if "opus" not in selected_model.lower():
            kwargs["temperature"] = temperature

        try:
            client = self._get_client()
            resp = await client.messages.create(**kwargs)
        except Exception as exc:
            raise LLMProviderError(f"Claude API error: {exc}") from exc

        content = "".join(
            block.text for block in resp.content if hasattr(block, "text")
        )
        usage = LLMUsage(
            prompt_tokens=resp.usage.input_tokens,
            completion_tokens=resp.usage.output_tokens,
        )
        cost = LLMResponse.calculate_cost(selected_model, usage)

        logger.debug(
            f"Claude [{selected_model}] task={task_type.value} "
            f"tokens={usage.total_tokens} cost=${cost:.6f}"
        )

        return LLMResponse(
            content=content,
            model=selected_model,
            provider=self.provider_name,
            usage=usage,
            task_type=task_type,
            cost_usd=cost,
            raw_response=resp,
        )
