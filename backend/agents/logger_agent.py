"""
LoggerAgent — логирование событий пайплайна в БД и файлы.

Пишет в:
1. PostgreSQL agent_logs
2. logs/app.log (общий лог приложения, ротация 30 дней)
3. logs/scraping.log (скрапинг события, ротация 30 дней)
4. logs/llm.log (LLM вызовы, ротация 30 дней)
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

# Файловые логгеры (настраиваются через logging_config.setup_logging())
_app_logger = logging.getLogger("cia.app")
_scraping_logger = logging.getLogger("cia.scraping")
_llm_logger = logging.getLogger("cia.llm")


class LoggerAgent:
    """Агент логирования — записывает события пайплайна."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._start_times: dict[str, float] = {}

    async def log_event(
        self,
        agent_name: str,
        event_type: str,
        message: str,
        details: Optional[dict] = None,
        duration_ms: Optional[int] = None,
        is_error: bool = False,
    ) -> None:
        """Записать событие в БД и файловый лог."""
        _app_logger.log(
            logging.ERROR if is_error else logging.INFO,
            f"[{self.session_id[:8]}] [{agent_name}] {event_type}: {message}",
        )
        # DB
        try:
            await self._write_db(
                agent_name=agent_name,
                event_type=event_type,
                message=message,
                details=details,
                duration_ms=duration_ms,
                is_error=is_error,
            )
        except Exception as exc:
            _app_logger.warning(f"DB log write failed: {exc}")

    async def log_scraping(
        self, collector_name: str, url: str, status: str, details: Optional[dict] = None
    ) -> None:
        _scraping_logger.info(
            f"[{self.session_id[:8]}] {collector_name} [{status}] {url}"
        )
        await self.log_event(
            agent_name=collector_name,
            event_type="source_tried" if status == "success" else "source_failed",
            message=f"{collector_name}: {status} — {url}",
            details=details,
            is_error=(status == "failed"),
        )

    async def log_llm_call(
        self,
        agent_name: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        task_description: str,
    ) -> None:
        _llm_logger.info(
            f"[{self.session_id[:8]}] {agent_name} → {provider}/{model} "
            f"tokens={prompt_tokens}+{completion_tokens} cost=${cost_usd:.6f} | {task_description}"
        )
        await self.log_event(
            agent_name=agent_name,
            event_type="llm_call",
            message=f"LLM: {provider}/{model} | {task_description}",
            details={
                "provider": provider,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "cost_usd": cost_usd,
            },
        )

    async def finalize_session(self) -> dict:
        """Финализировать сессию — вернуть сводку."""
        from llm.token_tracker import get_token_tracker
        summary = get_token_tracker().get_session_summary(self.session_id)
        await self.log_event(
            agent_name="logger_agent",
            event_type="completed",
            message=f"Session finalized. Total cost: ${summary.get('total_cost_usd', 0):.4f}",
            details=summary,
        )
        return summary

    async def _write_db(
        self,
        agent_name: str,
        event_type: str,
        message: str,
        details: Optional[dict],
        duration_ms: Optional[int],
        is_error: bool,
    ) -> None:
        from database import AsyncSessionLocal
        from models.token_log import AgentLog

        async with AsyncSessionLocal() as db:
            log_entry = AgentLog(
                session_id=uuid.UUID(self.session_id),
                agent_name=agent_name,
                event_type=event_type,
                message=message,
                details=details,
                duration_ms=duration_ms,
                is_error=is_error,
            )
            db.add(log_entry)
            await db.commit()
