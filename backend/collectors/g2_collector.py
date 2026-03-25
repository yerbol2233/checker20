"""
G2Collector — отзывы на платформе G2 (B2B-software reviews).

Извлекает: рейтинг, кол-во отзывов, pros/cons, категории,
наиболее частые жалобы — сигналы болей SDR-команд.
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


class G2Collector(BaseCollector):
    source_name = "g2"

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

        slug = re.sub(r"[^a-z0-9-]", "-", query.lower()).strip("-")
        product_url = f"https://www.g2.com/products/{slug}/reviews"

        try:
            html = await self.proxy.get_html(
                product_url, residential=True, render_js=False
            )
            data = self._parse(html, product_url)
            if not data.get("rating"):
                # Try search
                search_url = f"https://www.g2.com/search?query={quote_plus(query)}"
                html2 = await self.proxy.get_html(search_url)
                data = self._parse_search(html2, query) or data

            return CollectorResult(
                source_name=self.source_name,
                status="success" if data.get("rating") else "partial",
                data=data,
                retrieved_at=datetime.now(timezone.utc),
                url_used=product_url,
                confidence=0.8 if data.get("rating") else 0.3,
            )
        except Exception as exc:
            return make_failed_result(self.source_name, product_url, str(exc))

    def _parse(self, html: str, url: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        data: dict = {"url": url}
        text = soup.get_text(" ")

        # Рейтинг
        m = re.search(r"(\d+\.\d+)\s*out of\s*5", text, re.I)
        if m:
            data["rating"] = float(m.group(1))

        # Кол-во отзывов
        m2 = re.search(r"([\d,]+)\s+review", text, re.I)
        if m2:
            data["reviews_count"] = int(m2.group(1).replace(",", ""))

        # Категории / теги
        tags = []
        for tag in soup.find_all(
            ["span", "a"], {"class": re.compile(r"category|tag|badge", re.I)}
        ):
            t = tag.get_text(strip=True)
            if t and len(t) < 50:
                tags.append(t)
        if tags:
            data["categories"] = list(set(tags))[:10]

        # Pros / Cons snippets
        pros, cons = [], []
        for el in soup.find_all(
            string=re.compile(r"what do you like|pros?:", re.I)
        ):
            parent = el.parent
            if parent:
                pros.append(parent.get_text(strip=True)[:200])
        for el in soup.find_all(
            string=re.compile(r"what do you dislike|cons?:", re.I)
        ):
            parent = el.parent
            if parent:
                cons.append(parent.get_text(strip=True)[:200])
        data["pros_snippets"] = pros[:3]
        data["cons_snippets"] = cons[:3]

        return data

    def _parse_search(self, html: str, query: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        results = soup.find_all("a", href=re.compile(r"/products/.+/reviews"))
        if results:
            return {"search_result_url": "https://www.g2.com" + results[0]["href"]}
        return {}
