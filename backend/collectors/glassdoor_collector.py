"""
GlassdoorCollector — отзывы сотрудников и рейтинги компании.

Извлекает: рейтинг, отзывы (pros/cons), оценку CEO, рекомендации,
жалобы на процессы продаж/управления.
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
from scrapeops.parser_client import ScrapeOpsParserClient


class GlassdoorCollector(BaseCollector):
    source_name = "glassdoor"

    def __init__(self):
        super().__init__()
        self.proxy = ScrapeOpsProxyClient()
        self.parser = ScrapeOpsParserClient()

    async def collect(self, context: dict) -> CollectorResult:
        company_name = (
            context.get("company_name")
            or context.get("resolved_company_name", "")
        )
        domain = self.extract_domain(context.get("website_url", ""))
        query = company_name or domain
        if not query:
            return make_not_applicable_result(self.source_name, "No company name")

        search_url = (
            f"https://www.glassdoor.com/Search/results.htm"
            f"?keyword={quote_plus(query)}"
        )

        # Try Parser API first
        try:
            raw = await self.parser.extract(url=search_url, parser="glassdoor")
            if raw and raw.get("results"):
                company = raw["results"][0]
                return CollectorResult(
                    source_name=self.source_name,
                    status="success",
                    data=self._normalize(company),
                    retrieved_at=datetime.now(timezone.utc),
                    url_used=search_url,
                    confidence=0.8,
                )
        except Exception as exc:
            self.logger.debug(f"Parser API failed: {exc}")

        # Proxy fallback
        try:
            html = await self.proxy.get_html(
                search_url, residential=True, render_js=True
            )
            data = self._parse_search_html(html, query)
            return CollectorResult(
                source_name=self.source_name,
                status="partial" if data else "failed",
                data=data,
                retrieved_at=datetime.now(timezone.utc),
                url_used=search_url,
                confidence=0.55 if data else 0.0,
                error_message=None if data else "No results parsed",
            )
        except Exception as exc:
            return make_failed_result(self.source_name, search_url, str(exc))

    def _normalize(self, raw: dict) -> dict:
        return {
            "rating": raw.get("rating", 0),
            "reviews_count": raw.get("reviews_count", 0),
            "ceo_approval": raw.get("ceo_approval_rating", 0),
            "recommend_to_friend": raw.get("recommend_to_friend_pct", 0),
            "culture_rating": raw.get("culture_rating", 0),
            "work_life_balance": raw.get("work_life_balance_rating", 0),
            "senior_management": raw.get("senior_management_rating", 0),
            "comp_benefits": raw.get("comp_benefits_rating", 0),
            "career_opportunities": raw.get("career_opportunities_rating", 0),
            "recent_reviews": raw.get("reviews", [])[:5],
            "pros_summary": raw.get("pros", ""),
            "cons_summary": raw.get("cons", ""),
        }

    def _parse_search_html(self, html: str, query: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        data: dict = {"query": query}
        # Рейтинг
        rating_el = soup.find(
            ["span", "div"], {"class": re.compile(r"rating|score", re.I)}
        )
        if rating_el:
            txt = rating_el.get_text(strip=True)
            m = re.search(r"(\d+\.?\d*)", txt)
            if m:
                data["rating"] = float(m.group(1))
        # Кол-во отзывов
        reviews_el = soup.find(string=re.compile(r"\d+\s+review", re.I))
        if reviews_el:
            m = re.search(r"(\d+)", reviews_el)
            if m:
                data["reviews_count"] = int(m.group(1))
        return data
