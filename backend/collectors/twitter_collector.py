"""
TwitterCollector — публичная активность компании в Twitter/X.

Использует ScrapeOps Proxy для скрапинга публичного профиля.
Извлекает: кол-во подписчиков, твитов, частоту постинга, тональность.
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


class TwitterCollector(BaseCollector):
    source_name = "twitter"

    def __init__(self):
        super().__init__()
        self.proxy = ScrapeOpsProxyClient()

    async def collect(self, context: dict) -> CollectorResult:
        company_name = (
            context.get("company_name")
            or context.get("resolved_company_name", "")
        )
        domain = self.extract_domain(context.get("website_url", ""))
        query = company_name or domain
        if not query:
            return make_not_applicable_result(self.source_name, "No company name")

        # Пробуем угадать handle из domain
        handle = domain.split(".")[0] if domain else query.replace(" ", "").lower()
        profile_url = f"https://x.com/{handle}"

        try:
            html = await self.proxy.get_html(
                profile_url, residential=True, render_js=True
            )
            data = self._parse(html, profile_url)
            if not data.get("followers") and not data.get("tweets_count"):
                return CollectorResult(
                    source_name=self.source_name,
                    status="partial",
                    data={"handle_tried": handle, "note": "Profile may be private or not found"},
                    retrieved_at=datetime.now(timezone.utc),
                    url_used=profile_url,
                    confidence=0.2,
                )
            return CollectorResult(
                source_name=self.source_name,
                status="success",
                data=data,
                retrieved_at=datetime.now(timezone.utc),
                url_used=profile_url,
                confidence=0.7,
            )
        except Exception as exc:
            return make_failed_result(self.source_name, profile_url, str(exc))

    def _parse(self, html: str, url: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ")
        data: dict = {"profile_url": url}

        # Подписчики
        m = re.search(r"([\d.,]+[KkMm]?)\s*Followers", text)
        if m:
            data["followers"] = m.group(1)

        # Кол-во постов
        m2 = re.search(r"([\d.,]+[KkMm]?)\s*(?:Posts|Tweets)", text)
        if m2:
            data["tweets_count"] = m2.group(1)

        # Описание профиля
        bio = soup.find("div", {"data-testid": "UserDescription"})
        if bio:
            data["bio"] = bio.get_text(strip=True)[:300]

        # Дата создания
        m3 = re.search(r"Joined\s+(\w+\s+\d{4})", text)
        if m3:
            data["joined"] = m3.group(1)

        return data
