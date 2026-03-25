"""
BuiltWithCollector — технологический стек сайта компании.

Использует ScrapeOps Data API (tech-stack endpoint) или
прямой скрапинг builtwith.com через Proxy.

Извлекает: CRM, CMS, email-сервисы, аналитику, платёжные системы,
фреймворки — сигналы о зрелости IT-инфраструктуры.
"""
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from collectors.base import (
    BaseCollector, CollectorResult,
    make_failed_result, make_not_applicable_result,
)
from scrapeops.data_api_client import ScrapeOpsDataAPIClient
from scrapeops.proxy_client import ScrapeOpsProxyClient


# Технологии, важные для определения зрелости sales-процессов
SALES_TECH_KEYWORDS = [
    "salesforce", "hubspot", "pipedrive", "zoho", "outreach",
    "salesloft", "gong", "chorus", "drift", "intercom",
    "marketo", "pardot", "mailchimp", "klaviyo",
    "twilio", "ringcentral", "dialpad",
]


class BuiltWithCollector(BaseCollector):
    source_name = "builtwith"

    def __init__(self):
        super().__init__()
        self.data_api = ScrapeOpsDataAPIClient()
        self.proxy = ScrapeOpsProxyClient()

    async def collect(self, context: dict) -> CollectorResult:
        domain = self.extract_domain(context.get("website_url", ""))
        if not domain:
            return make_not_applicable_result(self.source_name, "No domain")

        # Попытка через Data API
        try:
            raw = await self.data_api.get_domain_tech_stack(domain)
            if raw and raw.get("technologies"):
                data = self._normalize_api(raw, domain)
                return CollectorResult(
                    source_name=self.source_name,
                    status="success",
                    data=data,
                    retrieved_at=datetime.now(timezone.utc),
                    url_used=f"https://api.scrapeops.io/v1/tech-stack?url={domain}",
                    confidence=0.9,
                )
        except Exception as exc:
            self.logger.debug(f"Data API failed: {exc}")

        # Fallback: скрапим builtwith.com
        bw_url = f"https://builtwith.com/{domain}"
        try:
            html = await self.proxy.get_html(bw_url, residential=False)
            data = self._parse_builtwith(html, domain)
            return CollectorResult(
                source_name=self.source_name,
                status="success" if data.get("technologies") else "partial",
                data=data,
                retrieved_at=datetime.now(timezone.utc),
                url_used=bw_url,
                confidence=0.75 if data.get("technologies") else 0.3,
            )
        except Exception as exc:
            return make_failed_result(self.source_name, bw_url, str(exc))

    def _normalize_api(self, raw: dict, domain: str) -> dict:
        techs = raw.get("technologies", [])
        names = [t.get("name", "") for t in techs if t.get("name")]
        return {
            "domain": domain,
            "technologies": names,
            "categories": list({t.get("category", "") for t in techs if t.get("category")}),
            "sales_tech_detected": [
                n for n in names
                if any(k in n.lower() for k in SALES_TECH_KEYWORDS)
            ],
            "total_count": len(names),
        }

    def _parse_builtwith(self, html: str, domain: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        techs: list[str] = []
        categories: list[str] = []

        for el in soup.find_all(
            ["a", "span"], {"class": re.compile(r"tech|tool|app", re.I)}
        ):
            name = el.get_text(strip=True)
            if name and 2 < len(name) < 50 and name not in techs:
                techs.append(name)

        for el in soup.find_all(["h3", "h4"], {"class": re.compile(r"category", re.I)}):
            cat = el.get_text(strip=True)
            if cat and cat not in categories:
                categories.append(cat)

        return {
            "domain": domain,
            "technologies": techs[:30],
            "categories": categories[:15],
            "sales_tech_detected": [
                t for t in techs
                if any(k in t.lower() for k in SALES_TECH_KEYWORDS)
            ],
            "total_count": len(techs),
        }
