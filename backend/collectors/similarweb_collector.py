"""
SimilarWebCollector — веб-трафик, источники, аудитория.

Извлекает: ежемесячные визиты, bounce rate, источники трафика,
топ страны, топ ключевые слова.
"""
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from collectors.base import (
    BaseCollector, CollectorResult,
    make_failed_result, make_not_applicable_result,
)
from scrapeops.proxy_client import ScrapeOpsProxyClient


class SimilarWebCollector(BaseCollector):
    source_name = "similarweb"

    def __init__(self):
        super().__init__()
        self.proxy = ScrapeOpsProxyClient()

    async def collect(self, context: dict) -> CollectorResult:
        domain = self.extract_domain(context.get("website_url", ""))
        if not domain:
            return make_not_applicable_result(self.source_name, "No domain")

        url = f"https://www.similarweb.com/website/{domain}/"

        try:
            html = await self.proxy.get_html(
                url, residential=True, render_js=True
            )
            data = self._parse(html, url, domain)
            return CollectorResult(
                source_name=self.source_name,
                status="success" if data.get("monthly_visits") else "partial",
                data=data,
                retrieved_at=datetime.now(timezone.utc),
                url_used=url,
                confidence=0.8 if data.get("monthly_visits") else 0.3,
            )
        except Exception as exc:
            return make_failed_result(self.source_name, url, str(exc))

    def _parse(self, html: str, url: str, domain: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ")
        data: dict = {"domain": domain, "url": url}

        # Ежемесячные визиты
        m = re.search(
            r"([\d,.]+[KkMmBb]?)\s*(?:total\s*)?(?:monthly\s*)?visits?",
            text,
            re.I,
        )
        if m:
            data["monthly_visits"] = m.group(1).strip()

        # Bounce rate
        m2 = re.search(r"bounce\s*rate[:\s]+([\d.]+)\s*%", text, re.I)
        if m2:
            data["bounce_rate_pct"] = float(m2.group(1))

        # Среднее время на сайте
        m3 = re.search(
            r"avg\.?\s+(?:visit\s+)?duration[:\s]+(\d+:\d+)", text, re.I
        )
        if m3:
            data["avg_visit_duration"] = m3.group(1)

        # Топ страны
        countries = re.findall(r"([A-Z]{2,3})\s+([\d.]+)\s*%", text)
        if countries:
            data["top_countries"] = [
                {"country": c[0], "pct": float(c[1])} for c in countries[:3]
            ]

        # Источники трафика
        traffic_sources = {}
        for source in ["Direct", "Organic Search", "Referrals", "Social", "Mail", "Paid Search"]:
            m4 = re.search(
                rf"{re.escape(source)}[:\s]+([\d.]+)\s*%", text, re.I
            )
            if m4:
                traffic_sources[source.lower().replace(" ", "_")] = float(m4.group(1))
        if traffic_sources:
            data["traffic_sources"] = traffic_sources

        return data
