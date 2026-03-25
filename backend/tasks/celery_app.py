import asyncio
from celery import Celery
from celery.schedules import crontab
from config import settings

celery_app = Celery(
    "cia",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["tasks.pipeline_task"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    # Beat schedule: периодические задачи
    beat_schedule={
        "cleanup-expired-cache": {
            "task": "tasks.pipeline_task.cleanup_expired_cache",
            "schedule": crontab(hour=3, minute=0),  # каждый день в 03:00 UTC
        },
    },
)


# ── Периодическая задача: очистка expired кеша ──────────────────────────

@celery_app.task(name="tasks.pipeline_task.cleanup_expired_cache")
def cleanup_expired_cache():
    """Удалить устаревшие записи кеша (старше 30 дней)."""
    from agents.memory import MemoryAgent
    memory = MemoryAgent()
    count = asyncio.run(memory.cleanup_expired())
    return {"cleaned": count}
