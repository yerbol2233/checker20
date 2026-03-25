"""
BaseCollector + CollectorResult.

Все коллекторы наследуют BaseCollector и возвращают CollectorResult.
Интерфейс зафиксирован в CLAUDE.md — не менять без обновления CLAUDE.md.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ── CollectorResult — канонический интерфейс (CLAUDE.md) ──────────────────

@dataclass
class CollectorResult:
    source_name: str
    status: str          # success | failed | partial | not_applicable
    data: dict
    retrieved_at: datetime
    url_used: str
    confidence: float    # 0.0 – 1.0
    error_message: Optional[str] = None

    def is_usable(self) -> bool:
        """True если данные можно использовать (success или partial)."""
        return self.status in ("success", "partial")

    def to_source_ref(self) -> dict:
        """Минимальная ссылка на источник для паспорта."""
        return {
            "source": self.source_name,
            "url": self.url_used,
            "retrieved_at": self.retrieved_at.isoformat(),
        }


def make_failed_result(
    source_name: str,
    url_used: str,
    error_message: str,
) -> CollectorResult:
    """Хелпер: создать результат с ошибкой."""
    return CollectorResult(
        source_name=source_name,
        status="failed",
        data={},
        retrieved_at=datetime.now(timezone.utc),
        url_used=url_used,
        confidence=0.0,
        error_message=error_message,
    )


def make_not_applicable_result(source_name: str, reason: str) -> CollectorResult:
    """Хелпер: источник не применим для данной компании."""
    return CollectorResult(
        source_name=source_name,
        status="not_applicable",
        data={},
        retrieved_at=datetime.now(timezone.utc),
        url_used="",
        confidence=0.0,
        error_message=reason,
    )


# ── BaseCollector ──────────────────────────────────────────────────────────

class BaseCollector(ABC):
    """
    Абстрактный базовый класс для всех коллекторов.

    Подклассы обязаны реализовать:
    - source_name: str — уникальное имя источника
    - collect(context) -> CollectorResult

    context — dict с входными данными сессии:
        {
            "website_url": str,
            "linkedin_lpr_url": str | None,
            "company_name": str | None,
            "resolved_domain": str | None,
        }
    """

    source_name: str = "base"

    def __init__(self):
        self.logger = logging.getLogger(
            f"{__name__}.{self.__class__.__name__}"
        )

    @abstractmethod
    async def collect(self, context: dict) -> CollectorResult:
        """
        Собрать данные из источника.

        Args:
            context: dict с входными данными (website_url, linkedin_lpr_url, etc.)

        Returns:
            CollectorResult с данными или ошибкой.
            НИКОГДА не выбрасывать исключения — перехватывать и возвращать failed.
        """
        ...

    async def safe_collect(self, context: dict) -> CollectorResult:
        """
        Обёртка с защитой от любых исключений.
        Всегда возвращает CollectorResult, никогда не падает.
        """
        try:
            return await self.collect(context)
        except Exception as exc:
            self.logger.error(
                f"[{self.source_name}] Unhandled exception: {exc}",
                exc_info=True,
            )
            return make_failed_result(
                source_name=self.source_name,
                url_used=context.get("website_url", ""),
                error_message=f"Unhandled error: {type(exc).__name__}: {exc}",
            )

    @staticmethod
    def extract_domain(url: str) -> str:
        """Извлечь домен из URL (без www, без схемы)."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        return host.removeprefix("www.").split(":")[0].strip("/")
