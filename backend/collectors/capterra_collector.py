"""
CapterraCollector — отзывы на Capterra (software reviews).

Извлекает: рейтинг, кол-во отзывов, pros/cons, категории.
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


class CapterraCollector(BaseCollector):
    source_name = "capterra"

    def __init__(self):
        super().__init__()
        self.proxy = ScrapeOpsProxyClient()

    async def collect(self, context: dict) -> CollectorResult:
        company_name = (
            context.get("company_name")
            or context.get("resolved_company_name", "")
        )
        if not company_name:
            company_name = self.extract_domain(context.get("website_url", ""))
        if not company_name:
            return make_not_applicable_result(self.source_name, "No company name")

        search_url = (
            f"https://www.capterra.com/search/?query={quote_plus(company_name)}"
        )

        try:
            html = await self.proxy.get_html(search_url, residential=True)
            data = self._parse(html, search_url, company_name)
            return CollectorResult(
                source_name=self.source_name,
                status="success" if data.get("rating") else "partial",
                data=data,
                retrieved_at=datetime.now(timezone.utc),
                url_used=search_url,
                confidence=0.75 if data.get("rating") else 0.3,
            )
        except Exception as exc:
            return make_failed_result(self.source_name, search_url, str(exc))

    def _parse(self, html: str, url: str, query: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ")
        data: dict = {"query": query, "url": url}

        m = re.search(r"(\d+\.\d+)\s*(?:out of|/)\s*5", text, re.I)
        if m:
            data["rating"] = float(m.group(1))

        m2 = re.search(r"([\d,]+)\s+review", text, re.I)
        if m2:
            data["reviews_count"] = int(m2.group(1).replace(",", ""))

        # Продукты из результатов поиска
        products = []
        for card in soup.find_all(
            ["div", "article"], {"class": re.compile(r"product|result|card", re.I)}
        )[:3]:
            name_el = card.find(["h2", "h3", "a"])
            if name_el:
                products.append(name_el.get_text(strip=True))
        if products:
            data["found_products"] = products

        return data
