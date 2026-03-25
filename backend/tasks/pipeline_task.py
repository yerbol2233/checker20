"""
Pipeline task — полная реализация пайплайна CIA через DispatcherAgent.

Шаг 7: end-to-end pipeline.
Запускается Celery (синхронный worker) → asyncio.run() для async пайплайна.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from celery.utils.log import get_task_logger
from sqlalchemy import select, update

from tasks.celery_app import celery_app
from database import AsyncSessionLocal
from models.session import Session

logger = get_task_logger(__name__)


async def _load_session_context(session_id: str) -> dict | None:
    """Загрузить данные сессии из БД и построить context для пайплайна."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Session).where(Session.id == uuid.UUID(session_id))
        )
        session = result.scalar_one_or_none()
        if not session:
            return None
        return {
            "website_url": session.website_url,
            "company_name": session.company_name or "",
            "linkedin_lpr_url": session.linkedin_lpr_url or "",
        }


async def _run_async_pipeline(session_id: str) -> dict:
    """
    Запустить полный пайплайн асинхронно.
    Создаёт aioredis-клиент и передаёт его в DispatcherAgent.
    """
    from config import settings

    # Загружаем контекст сессии из БД
    context = await _load_session_context(session_id)
    if not context:
        raise ValueError(f"Session {session_id} not found in DB")

    logger.info(
        f"[{session_id}] Starting pipeline for {context['website_url']}"
    )

    # Создаём async redis-клиент для SSE pub/sub
    import redis.asyncio as aioredis
    redis_client = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )

    try:
        from agents.dispatcher import DispatcherAgent
        dispatcher = DispatcherAgent(redis_client=redis_client)
        result = await dispatcher.run(session_id, context)
        logger.info(f"[{session_id}] Pipeline result: {result}")
        return result
    finally:
        await redis_client.aclose()


async def _mark_session_failed(session_id: str, error: str) -> None:
    """Пометить сессию как failed в БД (fallback при краше)."""
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Session)
                .where(Session.id == uuid.UUID(session_id))
                .values(
                    status="failed",
                    pipeline_finished_at=datetime.now(timezone.utc),
                    errors=[{"error": error, "at": datetime.now(timezone.utc).isoformat()}],
                )
            )
            await db.commit()
    except Exception as exc:
        logger.error(f"Failed to mark session {session_id} as failed: {exc}")


@celery_app.task(
    bind=True,
    name="tasks.pipeline_task.run_pipeline",
    max_retries=0,           # Не ретраим — pipeline сам обрабатывает ошибки
    acks_late=True,          # Ack только после завершения (надёжность)
    time_limit=600,          # 10 минут максимум
    soft_time_limit=540,     # Soft kill за 9 минут
)
def run_pipeline(self, session_id: str) -> dict:
    """
    Основная Celery задача пайплайна.
    Запускает асинхронный DispatcherAgent через asyncio.run().
    """
    logger.info(f"Celery task started: session_id={session_id}")

    try:
        result = asyncio.run(_run_async_pipeline(session_id))
        logger.info(f"Celery task completed: session_id={session_id}, result={result}")
        return result
    except Exception as exc:
        logger.error(
            f"Celery task FAILED: session_id={session_id}, error={exc}",
            exc_info=True,
        )
        # Гарантированно помечаем сессию как failed
        asyncio.run(_mark_session_failed(session_id, str(exc)))
        # Не ретраим — возвращаем статус failed
        return {"status": "failed", "session_id": session_id, "error": str(exc)}
