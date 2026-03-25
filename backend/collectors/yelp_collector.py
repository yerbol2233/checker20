"""
YelpCollector — отзывы на Yelp (для B2C-компаний с физическим присутствием).

Извлекает: рейтинг, кол-во отзывов, категории бизнеса, последние отзывы.
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


class YelpCollector(BaseCollector):
    source_name = "yelp"

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
            f"https://www.yelp.com/search?find_desc={quote_plus(company_name)}"
        )

        try:
            html = await self.proxy.get_html(search_url, residential=False)
            data = self._parse(html, search_url, company_name)
            return CollectorResult(
                source_name=self.source_name,
                status="success" if data.get("rating") else "partial",
                data=data,
                retrieved_at=datetime.now(timezone.utc),
                url_used=search_url,
                confidence=0.65 if data.get("rating") else 0.2,
            )
        except Exception as exc:
            return make_failed_result(self.source_name, search_url, str(exc))

    def _parse(self, html: str, url: str, query: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ")
        data: dict = {"query": query}

        m = re.search(r"(\d+\.?\d*)\s*(?:star|rating)", text, re.I)
        if m:
            data["rating"] = float(m.group(1))

        m2 = re.search(r"([\d,]+)\s+review", text, re.I)
        if m2:
            data["reviews_count"] = int(m2.group(1).replace(",", ""))

        # Категории
        cats = []
        for el in soup.find_all(
            ["span", "a"], {"class": re.compile(r"category|tag", re.I)}
        )[:5]:
            t = el.get_text(strip=True)
            if t and len(t) < 30:
                cats.append(t)
        data["categories"] = list(set(cats))

        return data
