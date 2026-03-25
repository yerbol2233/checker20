"""
GoogleReviewsCollector — отзывы Google Maps / Google Business.

Использует ScrapeOps Proxy + scraping google maps search.
Извлекает: рейтинг, кол-во отзывов, адрес, телефон.
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


class GoogleReviewsCollector(BaseCollector):
    source_name = "google_reviews"

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

        # Google search для получения Knowledge Graph / рейтинга
        search_url = (
            f"https://www.google.com/search"
            f"?q={quote_plus(query + ' reviews site:google.com OR reviews')}"
        )

        try:
            html = await self.proxy.get_html(
                search_url, residential=True, render_js=False
            )
            data = self._parse(html, search_url, query)
            return CollectorResult(
                source_name=self.source_name,
                status="success" if data.get("rating") else "partial",
                data=data,
                retrieved_at=datetime.now(timezone.utc),
                url_used=search_url,
                confidence=0.7 if data.get("rating") else 0.25,
            )
        except Exception as exc:
            return make_failed_result(self.source_name, search_url, str(exc))

    def _parse(self, html: str, url: str, query: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ")
        data: dict = {"query": query}

        # Рейтинг (паттерн "4.2 stars" или "4.2 (1,234 reviews)")
        m = re.search(r"(\d+\.?\d*)\s*(?:stars?|★)", text, re.I)
        if m:
            val = float(m.group(1))
            if 1.0 <= val <= 5.0:
                data["rating"] = val

        # Кол-во отзывов
        m2 = re.search(r"([\d,]+)\s+(?:Google\s+)?review", text, re.I)
        if m2:
            data["reviews_count"] = int(m2.group(1).replace(",", ""))

        # Адрес
        addr = soup.find(attrs={"data-attrid": re.compile(r"address", re.I)})
        if addr:
            data["address"] = addr.get_text(strip=True)

        return data
