"""
GET /sessions/{id}/stream — SSE поток событий пайплайна.

События публикуются из Celery worker в Redis pub/sub канал.
Этот endpoint подписывается на канал и стримит события клиенту.
"""
import asyncio
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
import redis.asyncio as aioredis

from config import settings
from models.session import Session

router = APIRouter(prefix="/sessions", tags=["stream"])

SSE_CHANNEL_PREFIX = "sse:session:"
SSE_HEARTBEAT_INTERVAL = 15  # секунд
SSE_TIMEOUT = 600  # 10 минут максимум


def _sse_format(data: str) -> str:
    """Форматировать SSE-сообщение (без named event — всё идёт в onmessage)."""
    return f"data: {data}\n\n"


async def _event_generator(
    session_id: str, request: Request
) -> AsyncGenerator[str, None]:
    """Генератор SSE событий из Redis pub/sub."""
    channel = f"{SSE_CHANNEL_PREFIX}{session_id}"

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)

    # Начальное событие — подтверждение подключения
    yield _sse_format(
        json.dumps({"type": "connected", "session_id": session_id})
    )

    # Также check if session already completed (race condition prevention)
    try:
        from database import AsyncSessionLocal
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Session).where(Session.id == uuid.UUID(session_id))
            )
            sess = result.scalar_one_or_none()
            if sess and sess.status in ("completed", "cached"):
                yield _sse_format(
                    json.dumps({"type": "pipeline_completed",
                                "message": "Pipeline already completed"})
                )
                return
            if sess and sess.status == "failed":
                yield _sse_format(
                    json.dumps({"type": "pipeline_failed",
                                "message": "Pipeline failed"})
                )
                return
    except Exception:
        pass  # Non-critical, continue with streaming

    elapsed = 0.0
    try:
        while elapsed < SSE_TIMEOUT:
            # Проверяем, не отключился ли клиент
            if await request.is_disconnected():
                break

            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0
            )

            if message and message["type"] == "message":
                data = message["data"]
                try:
                    parsed = json.loads(data)
                    event_type = parsed.get("type", "event")
                    yield _sse_format(data)

                    # Завершаем стрим при финальных событиях
                    if event_type in ("pipeline_completed", "pipeline_failed"):
                        break
                except json.JSONDecodeError:
                    yield _sse_format(data)
            else:
                # Heartbeat каждые N секунд
                elapsed += 1.0
                if int(elapsed) % SSE_HEARTBEAT_INTERVAL == 0:
                    yield _sse_format(
                        json.dumps({"type": "heartbeat"})
                    )

    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await r.aclose()


@router.get("/{session_id}/stream")
async def stream_session(session_id: str, request: Request) -> StreamingResponse:
    """SSE поток событий для сессии анализа."""
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id format")

    return StreamingResponse(
        _event_generator(session_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

