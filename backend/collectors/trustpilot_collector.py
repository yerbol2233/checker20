"""
TrustpilotCollector — потребительские отзывы (B2C-репутация).

Извлекает: TrustScore, кол-во отзывов, распределение по звёздам,
последние отзывы, темы жалоб.
"""
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from collectors.base import (
    BaseCollector, CollectorResult,
    make_failed_result, make_not_applicable_result,
)
from scrapeops.proxy_client import ScrapeOpsProxyClient


class TrustpilotCollector(BaseCollector):
    source_name = "trustpilot"

    def __init__(self):
        super().__init__()
        self.proxy = ScrapeOpsProxyClient()

    async def collect(self, context: dict) -> CollectorResult:
        domain = self.extract_domain(context.get("website_url", ""))
        if not domain:
            return make_not_applicable_result(self.source_name, "No domain")

        review_url = f"https://www.trustpilot.com/review/{domain}"

        try:
            html = await self.proxy.get_html(review_url, residential=False)
            data = self._parse(html, review_url)
            return CollectorResult(
                source_name=self.source_name,
                status="success" if data.get("trust_score") else "partial",
                data=data,
                retrieved_at=datetime.now(timezone.utc),
                url_used=review_url,
                confidence=0.85 if data.get("trust_score") else 0.3,
            )
        except Exception as exc:
            return make_failed_result(self.source_name, review_url, str(exc))

    def _parse(self, html: str, url: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        data: dict = {"url": url}

        # TrustScore
        score_el = soup.find(attrs={"data-rating-typography": True})
        if not score_el:
            score_el = soup.find(
                ["span", "p"], {"class": re.compile(r"score|rating|trust", re.I)}
            )
        if score_el:
            m = re.search(r"(\d+\.?\d*)", score_el.get_text())
            if m:
                data["trust_score"] = float(m.group(1))

        # Кол-во отзывов
        text = soup.get_text(" ")
        m2 = re.search(r"([\d,]+)\s+(?:total\s+)?review", text, re.I)
        if m2:
            data["reviews_count"] = int(m2.group(1).replace(",", ""))

        # Распределение звёзд (ищем 5★/4★/... паттерны)
        stars = {}
        for m in re.finditer(r"(\d+)\s*%.*?(\d)\s*star", text, re.I):
            stars[f"{m.group(2)}_star_pct"] = int(m.group(1))
        if stars:
            data["stars_distribution"] = stars

        # Последние отзывы
        reviews = []
        for rev in soup.find_all(
            ["article", "div"], {"class": re.compile(r"review|testimonial", re.I)}
        )[:5]:
            body = rev.find(
                ["p", "span"], {"class": re.compile(r"body|text|content", re.I)}
            )
            if body:
                reviews.append(body.get_text(strip=True)[:200])
        data["recent_reviews"] = reviews

        return data
