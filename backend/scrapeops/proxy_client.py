"""
ScrapeOps Proxy API клиент.

Используется для скрапинга любого URL через прокси ScrapeOps:
https://proxy.scrapeops.io/v1/?api_key=KEY&url=TARGET_URL

Документация: https://scrapeops.io/docs/proxy-aggregator/integration-guides/python-requests/
"""
import logging
from typing import Optional
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

PROXY_BASE_URL = "https://proxy.scrapeops.io/v1/"
DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3


class ScrapeOpsProxyClient:
    """
    Асинхронный клиент ScrapeOps Proxy API.

    Пример использования:
        client = ScrapeOpsProxyClient()
        html = await client.get("https://example.com")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key or settings.scrapeops_api_key
        self.timeout = timeout

    def _build_proxy_url(
        self,
        target_url: str,
        country: str = "us",
        residential: bool = False,
        render_js: bool = False,
        wait_for_selector: Optional[str] = None,
    ) -> str:
        """Строит URL запроса к Proxy API."""
        params: dict = {
            "api_key": self.api_key,
            "url": target_url,
        }
        if country:
            params["country"] = country
        if residential:
            params["residential"] = "true"
        if render_js:
            params["render_js"] = "true"
        if wait_for_selector:
            params["wait_for_selector"] = wait_for_selector

        return PROXY_BASE_URL + "?" + urlencode(params)

    @retry(
        stop=stop_after_attempt(DEFAULT_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    async def get(
        self,
        url: str,
        country: str = "us",
        residential: bool = False,
        render_js: bool = False,
        wait_for_selector: Optional[str] = None,
        extra_headers: Optional[dict] = None,
    ) -> httpx.Response:
        """
        Выполнить GET-запрос через ScrapeOps Proxy.

        Returns:
            httpx.Response с HTML-содержимым страницы.
        Raises:
            httpx.HTTPStatusError: при 4xx/5xx ответе.
            httpx.TimeoutException: при таймауте (будет повторено).
        """
        proxy_url = self._build_proxy_url(
            target_url=url,
            country=country,
            residential=residential,
            render_js=render_js,
            wait_for_selector=wait_for_selector,
        )

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        }
        if extra_headers:
            headers.update(extra_headers)

        logger.debug(f"ScrapeOps proxy GET: {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(proxy_url, headers=headers)
            response.raise_for_status()
            return response

    async def get_html(
        self,
        url: str,
        country: str = "us",
        residential: bool = False,
        render_js: bool = False,
    ) -> str:
        """Возвращает HTML текст страницы (shorthand)."""
        resp = await self.get(
            url,
            country=country,
            residential=residential,
            render_js=render_js,
        )
        return resp.text
