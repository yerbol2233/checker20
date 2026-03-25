"""
ScrapeOps Data API клиент.

Используется для доступа к заранее собранным данным о компаниях
и технологическом стеке через ScrapeOps Data API.

Документация: https://scrapeops.io/docs/fake-user-agent-api/ (Headers & Data API)
"""
import logging
from typing import Optional, Any
from urllib.parse import urlencode

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config import settings

logger = logging.getLogger(__name__)

DATA_API_BASE_URL = "https://api.scrapeops.io/v1/"
DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3


class ScrapeOpsDataAPIClient:
    """
    Асинхронный клиент ScrapeOps Data API.

    Даёт доступ к:
    - fake browser headers (для реалистичных запросов)
    - технологическому стеку домена
    - общей информации о домене
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key or settings.scrapeops_api_key
        self.timeout = timeout

    @retry(
        stop=stop_after_attempt(DEFAULT_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    async def _get(self, endpoint: str, params: dict) -> dict[str, Any]:
        """Базовый GET запрос к Data API."""
        params["api_key"] = self.api_key
        url = DATA_API_BASE_URL + endpoint + "?" + urlencode(params)
        logger.debug(f"ScrapeOps data API: {endpoint} params={params}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def get_fake_headers(
        self, num_results: int = 1, browser_type: str = "chrome"
    ) -> list[dict]:
        """
        Получить реалистичные browser headers.
        Используется для скрапинга без прокси (базовые запросы).
        """
        data = await self._get(
            "fake-browser-headers",
            {"num_results": num_results, "browser_type": browser_type},
        )
        return data.get("result", [])

    async def get_domain_tech_stack(self, domain: str) -> dict[str, Any]:
        """
        Получить данные о технологическом стеке домена.
        Аналог BuiltWith — какие технологии использует сайт.
        """
        return await self._get("tech-stack", {"url": domain})

    async def get_domain_info(self, domain: str) -> dict[str, Any]:
        """Получить общую информацию о домене."""
        return await self._get("domain-info", {"url": domain})
