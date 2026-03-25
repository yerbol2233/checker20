"""
OpenAIClient — OpenAI GPT провайдер (fallback).

Модель: gpt-4o-mini
Используется когда Claude и Gemini недоступны.
"""
import logging
from typing import Optional

from llm.base import (
    LLMProvider, LLMResponse, LLMUsage, TaskType,
    TOKEN_COSTS_USD, LLMProviderError,
)
from config import settings

logger = logging.getLogger(__name__)

FALLBACK_MODEL = "gpt-4o-mini"


class OpenAIClient(LLMProvider):
    provider_name = "openai"
    default_model = FALLBACK_MODEL

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or settings.openai_api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self._api_key)
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
            raise LLMProviderError("OpenAI API key not configured")

        selected_model = model or self.default_model

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            client = self._get_client()
            resp = await client.chat.completions.create(
                model=selected_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            raise LLMProviderError(f"OpenAI API error: {exc}") from exc

        content = resp.choices[0].message.content or ""
        usage = LLMUsage(
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
        )
        cost = LLMResponse.calculate_cost(selected_model, usage)

        logger.debug(
            f"OpenAI [{selected_model}] task={task_type.value} "
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
