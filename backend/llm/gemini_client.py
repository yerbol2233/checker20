"""
GeminiClient — Google Gemini провайдер.

Модель: gemini-2.5-flash
Задачи: валидация данных, классификация, scoring, приоритизация.
"""
import logging
from typing import Optional

from llm.base import (
    LLMProvider, LLMResponse, LLMUsage, TaskType,
    TASK_TO_MODEL, TOKEN_COSTS_USD, LLMProviderError,
)
from config import settings

logger = logging.getLogger(__name__)


class GeminiClient(LLMProvider):
    provider_name = "gemini"
    default_model = "gemini-2.5-flash"

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or settings.google_api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            self._client = genai
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
            raise LLMProviderError("Google API key not configured")

        selected_model = model or TASK_TO_MODEL.get(task_type, self.default_model)

        # Gemini использует sync API через asyncio executor
        import asyncio

        try:
            genai = self._get_client()
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: genai.GenerativeModel(
                    model_name=selected_model,
                    generation_config=generation_config,
                ).generate_content(full_prompt),
            )
        except Exception as exc:
            raise LLMProviderError(f"Gemini API error: {exc}") from exc

        content = response.text if hasattr(response, "text") else ""

        # Gemini API возвращает usage_metadata
        usage_meta = getattr(response, "usage_metadata", None)
        if usage_meta:
            prompt_tokens = getattr(usage_meta, "prompt_token_count", 0) or 0
            completion_tokens = getattr(usage_meta, "candidates_token_count", 0) or 0
        else:
            # Fallback: грубая оценка
            prompt_tokens = len(full_prompt.split()) * 2
            completion_tokens = len(content.split()) * 2

        usage = LLMUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        cost = LLMResponse.calculate_cost(selected_model, usage)

        logger.debug(
            f"Gemini [{selected_model}] task={task_type.value} "
            f"tokens={usage.total_tokens} cost=${cost:.6f}"
        )

        return LLMResponse(
            content=content,
            model=selected_model,
            provider=self.provider_name,
            usage=usage,
            task_type=task_type,
            cost_usd=cost,
            raw_response=response,
        )
