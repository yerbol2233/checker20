"""
MemoryAgent — кеш паспортов компаний (30 дней).

Логика:
- При запросе проверяем company_cache по домену
- Если запись свежая (< TTL) — возвращаем кешированные данные
- Outreach НЕ кешируется (всегда генерируется заново)
- Сохранение паспорта → обновляем company_cache
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, delete

from database import AsyncSessionLocal
from models.session import Session
from models.passport import Passport
from models.outreach import OutreachText
from models.token_log import CompanyCache
from config import settings
import logging

logger = logging.getLogger(__name__)


class MemoryAgent:
    """Управление кешем паспортов."""

    def __init__(self):
        self.ttl_days = settings.company_cache_ttl_days

    async def check_cache(self, domain: str) -> Optional[dict]:
        """
        Проверить кеш по домену.

        Returns:
            dict с cached_passport и session_id если кеш свежий, иначе None.
        """
        if not domain:
            return None

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CompanyCache).where(
                    CompanyCache.domain == domain,
                    CompanyCache.expires_at > datetime.now(timezone.utc),
                )
            )
            cache_entry = result.scalar_one_or_none()

            if not cache_entry:
                return None

            # Загружаем паспорт
            if cache_entry.passport_id:
                passport_result = await db.execute(
                    select(Passport).where(Passport.id == cache_entry.passport_id)
                )
                passport = passport_result.scalar_one_or_none()
                if passport:
                    logger.info(f"Cache HIT for domain: {domain} (cached {cache_entry.cached_at})")
                    return {
                        "passport_id": str(passport.id),
                        "session_id": str(cache_entry.last_session_id),
                        "cached_at": cache_entry.cached_at.isoformat(),
                        "expires_at": cache_entry.expires_at.isoformat(),
                        "passport": passport,
                    }

        return None

    async def save_passport(
        self,
        session_id: str,
        domain: str,
        passport: Passport,
    ) -> None:
        """Сохранить паспорт и обновить кеш."""
        async with AsyncSessionLocal() as db:
            # Upsert company_cache
            result = await db.execute(
                select(CompanyCache).where(CompanyCache.domain == domain)
            )
            cache_entry = result.scalar_one_or_none()

            now = datetime.now(timezone.utc)
            expires = now + timedelta(days=self.ttl_days)

            if cache_entry:
                cache_entry.last_session_id = uuid.UUID(session_id)
                cache_entry.passport_id = passport.id
                cache_entry.cached_at = now
                cache_entry.expires_at = expires
            else:
                cache_entry = CompanyCache(
                    domain=domain,
                    last_session_id=uuid.UUID(session_id),
                    passport_id=passport.id,
                    cached_at=now,
                    expires_at=expires,
                )
                db.add(cache_entry)

            await db.commit()
            logger.info(f"Passport cached for domain: {domain} (expires {expires.date()})")

    async def save_outreach(
        self, session_id: str, outreach: OutreachText
    ) -> None:
        """Сохранить outreach (НЕ кешируется, только в таблицу)."""
        async with AsyncSessionLocal() as db:
            db.add(outreach)
            await db.commit()

    async def invalidate_cache(self, domain: str) -> None:
        """Принудительно инвалидировать кеш домена."""
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(CompanyCache).where(CompanyCache.domain == domain)
            )
            await db.commit()
            logger.info(f"Cache invalidated for domain: {domain}")

    async def cleanup_expired(self) -> int:
        """Удалить устаревшие записи кеша (Celery beat задача)."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(CompanyCache).where(
                    CompanyCache.expires_at <= datetime.now(timezone.utc)
                )
            )
            await db.commit()
            count = result.rowcount
            if count:
                logger.info(f"Cleaned up {count} expired cache entries")
            return count
