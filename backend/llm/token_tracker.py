"""
TokenTracker — трекинг токенов и стоимости LLM-запросов.

Пишет в:
1. PostgreSQL таблицу token_logs (через SQLAlchemy async)
2. CSV файл logs/token_costs.csv (append)
3. In-memory аккумулятор на сессию (для финального отчёта)
"""
import csv
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from llm.base import LLMUsage, TaskType

logger = logging.getLogger(__name__)

LOGS_DIR = Path(__file__).parent.parent / "logs"
TOKEN_CSV_PATH = LOGS_DIR / "token_costs.csv"

CSV_HEADERS = [
    "session_id", "timestamp", "agent_name", "task_type",
    "llm_provider", "model_name",
    "prompt_tokens", "completion_tokens", "total_tokens",
    "cost_usd",
]


class TokenTracker:
    """
    Трекер токенов. Один экземпляр на сессию (или синглтон).
    """

    def __init__(self):
        self._session_totals: dict[str, dict] = {}
        LOGS_DIR.mkdir(exist_ok=True)

    async def log(
        self,
        session_id: str,
        agent_name: str,
        llm_provider: str,
        model_name: str,
        usage: LLMUsage,
        cost_usd: float,
        task_type: TaskType = TaskType.GENERAL,
        task_description: Optional[str] = None,
    ) -> None:
        """Записать использование токенов в CSV и БД."""
        now = datetime.now(timezone.utc)

        # 1. In-memory аккумулятор
        self._accumulate(session_id, llm_provider, model_name, usage, cost_usd)

        # 2. CSV
        self._write_csv(
            session_id=session_id,
            timestamp=now,
            agent_name=agent_name,
            task_type=task_type.value,
            llm_provider=llm_provider,
            model_name=model_name,
            usage=usage,
            cost_usd=cost_usd,
        )

        # 3. БД (async, не критично при ошибке)
        try:
            await self._write_db(
                session_id=session_id,
                agent_name=agent_name,
                llm_provider=llm_provider,
                model_name=model_name,
                usage=usage,
                cost_usd=cost_usd,
                task_description=task_description,
            )
        except Exception as exc:
            logger.warning(f"TokenTracker DB write failed (non-critical): {exc}")

    def get_session_summary(self, session_id: str) -> dict:
        """Получить сводку расходов для сессии."""
        return self._session_totals.get(session_id, {
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "by_provider": {},
        })

    def _accumulate(
        self,
        session_id: str,
        provider: str,
        model: str,
        usage: LLMUsage,
        cost: float,
    ) -> None:
        if session_id not in self._session_totals:
            self._session_totals[session_id] = {
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "by_provider": {},
            }
        s = self._session_totals[session_id]
        s["total_tokens"] += usage.total_tokens
        s["total_cost_usd"] = round(s["total_cost_usd"] + cost, 8)

        if provider not in s["by_provider"]:
            s["by_provider"][provider] = {
                "tokens": 0, "cost_usd": 0.0, "calls": 0, "models": []
            }
        p = s["by_provider"][provider]
        p["tokens"] += usage.total_tokens
        p["cost_usd"] = round(p["cost_usd"] + cost, 8)
        p["calls"] += 1
        if model not in p["models"]:
            p["models"].append(model)

    def _write_csv(
        self,
        session_id: str,
        timestamp: datetime,
        agent_name: str,
        task_type: str,
        llm_provider: str,
        model_name: str,
        usage: LLMUsage,
        cost_usd: float,
    ) -> None:
        try:
            file_exists = TOKEN_CSV_PATH.exists()
            with open(TOKEN_CSV_PATH, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                if not file_exists:
                    writer.writeheader()
                writer.writerow({
                    "session_id": session_id,
                    "timestamp": timestamp.isoformat(),
                    "agent_name": agent_name,
                    "task_type": task_type,
                    "llm_provider": llm_provider,
                    "model_name": model_name,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost_usd": round(cost_usd, 8),
                })
        except Exception as exc:
            logger.warning(f"TokenTracker CSV write failed: {exc}")

    async def _write_db(
        self,
        session_id: str,
        agent_name: str,
        llm_provider: str,
        model_name: str,
        usage: LLMUsage,
        cost_usd: float,
        task_description: Optional[str],
    ) -> None:
        from database import AsyncSessionLocal
        from models.token_log import TokenLog

        async with AsyncSessionLocal() as db:
            token_log = TokenLog(
                session_id=uuid.UUID(session_id),
                agent_name=agent_name,
                llm_provider=llm_provider,
                model_name=model_name,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                cost_usd=cost_usd,
                task_description=task_description,
            )
            db.add(token_log)
            await db.commit()


# Синглтон для использования в агентах
_token_tracker_instance: Optional[TokenTracker] = None


def get_token_tracker() -> TokenTracker:
    global _token_tracker_instance
    if _token_tracker_instance is None:
        _token_tracker_instance = TokenTracker()
    return _token_tracker_instance
