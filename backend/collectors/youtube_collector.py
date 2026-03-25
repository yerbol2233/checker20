"""
YouTubeCollector — YouTube-канал компании и видео-активность.

Использует ScrapeOps Proxy + скрапинг YouTube search.
Без API ключа (публичный поиск).

Извлекает: наличие канала, кол-во подписчиков, частота публикаций,
типы видео (демо, вебинары, отзывы клиентов).
"""
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from collectors.base import (
    BaseCollector, CollectorResult,
    make_failed_result, make_not_applicable_result,
)
from scrapeops.proxy_client import ScrapeOpsProxyClient


class YouTubeCollector(BaseCollector):
    source_name = "youtube"

    def __init__(self):
        super().__init__()
        self.proxy = ScrapeOpsProxyClient()

    async def collect(self, context: dict) -> CollectorResult:
        company_name = (
            context.get("company_name")
            or context.get("resolved_company_name", "")
        )
        if not company_name:
            return make_not_applicable_result(self.source_name, "No company name")

        search_url = (
            f"https://www.youtube.com/results"
            f"?search_query={quote_plus(company_name)}"
            f"&sp=EgIQAg%3D%3D"  # фильтр: каналы
        )

        try:
            html = await self.proxy.get_html(
                search_url, residential=False, render_js=False
            )
            data = self._parse(html, search_url, company_name)
            return CollectorResult(
                source_name=self.source_name,
                status="success" if data.get("channel_found") else "partial",
                data=data,
                retrieved_at=datetime.now(timezone.utc),
                url_used=search_url,
                confidence=0.7 if data.get("subscribers") else 0.3,
            )
        except Exception as exc:
            return make_failed_result(self.source_name, search_url, str(exc))

    def _parse(self, html: str, url: str, query: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ")
        data: dict = {"query": query, "channel_found": False}

        # Ищем упоминание подписчиков
        m = re.search(r"([\d.]+[KkMm]?)\s*subscriber", text, re.I)
        if m:
            data["subscribers"] = m.group(1)
            data["channel_found"] = True

        # Ищем видео компании
        video_titles = re.findall(
            r'"title":\s*\{"runs":\s*\[\{"text":\s*"([^"]{10,80})"', html
        )
        if video_titles:
            data["recent_video_titles"] = video_titles[:5]

        # Типы контента
        content_types = []
        for keyword in ["demo", "webinar", "tutorial", "review", "customer story", "case study"]:
            if keyword.lower() in text.lower():
                content_types.append(keyword)
        data["content_types"] = content_types

        # Кол-во видео
        m2 = re.search(r"([\d,]+)\s+video", text, re.I)
        if m2:
            data["videos_count"] = m2.group(1).replace(",", "")

        return data
