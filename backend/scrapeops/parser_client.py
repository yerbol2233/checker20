"""
ScrapeOps Parser API клиент.

Используется для структурированного извлечения данных с известных платформ
(LinkedIn, Glassdoor, G2, etc.) через ScrapeOps Parser API.

Документация: https://scrapeops.io/docs/data-parser-api/
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

PARSER_BASE_URL = "https://api.scrapeops.io/v1/"
DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3


class ScrapeOpsParserClient:
    """
    Асинхронный клиент ScrapeOps Parser API.

    Умеет извлекать структурированные данные с:
    - LinkedIn (компании, профили)
    - Google Maps / Reviews
    - Glassdoor
    - и других платформ через endpoint /extract
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
    async def extract(
        self,
        url: str,
        parser: Optional[str] = None,
        country: str = "us",
        residential: bool = False,
    ) -> dict[str, Any]:
        """
        Извлечь структурированные данные через Parser API.

        Args:
            url: целевой URL для парсинга
            parser: явное указание парсера (linkedin-company, glassdoor, etc.)
                    если None — ScrapeOps определит автоматически
            country: страна прокси
            residential: использовать резидентные прокси

        Returns:
            dict с извлечёнными данными
        """
        params: dict = {
            "api_key": self.api_key,
            "url": url,
            "country": country,
        }
        if residential:
            params["residential"] = "true"
        if parser:
            params["parser"] = parser

        endpoint = PARSER_BASE_URL + "extract?" + urlencode(params)
        logger.debug(f"ScrapeOps parser extract: {url} (parser={parser})")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(endpoint)
            response.raise_for_status()
            return response.json()

    async def extract_linkedin_company(self, linkedin_url: str) -> dict[str, Any]:
        """Извлечь данные страницы компании LinkedIn."""
        return await self.extract(url=linkedin_url, parser="linkedin-company")

    async def extract_linkedin_profile(self, profile_url: str) -> dict[str, Any]:
        """Извлечь данные профиля LinkedIn."""
        return await self.extract(url=profile_url, parser="linkedin-profile")

    async def extract_glassdoor(self, glassdoor_url: str) -> dict[str, Any]:
        """Извлечь данные с Glassdoor."""
        return await self.extract(url=glassdoor_url, parser="glassdoor")
