"""
ApolloCollector — данные об организации и контактах через Apollo.io.

Apollo.io предоставляет API для поиска компаний и людей.
API ключ не обязателен для базового поиска (использует публичный поиск).

Извлекает: размер компании, отрасль, технологии, ключевые люди,
email-паттерны.
"""
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from collectors.base import (
    BaseCollector, CollectorResult,
    make_failed_result, make_not_applicable_result,
)
from scrapeops.proxy_client import ScrapeOpsProxyClient


class ApolloCollector(BaseCollector):
    source_name = "apollo"

    def __init__(self):
        super().__init__()
        self.proxy = ScrapeOpsProxyClient()

    async def collect(self, context: dict) -> CollectorResult:
        domain = self.extract_domain(context.get("website_url", ""))
        company_name = (
            context.get("company_name")
            or context.get("resolved_company_name", "")
        )
        if not domain and not company_name:
            return make_not_applicable_result(self.source_name, "No domain or company name")

        # Apollo публичный поиск по домену
        search_query = domain or company_name
        search_url = (
            f"https://app.apollo.io/#/companies"
            f"?q_organization_domains[]={quote_plus(search_query)}"
        )

        # Используем публичный Apollo API endpoint
        api_url = (
            f"https://api.apollo.io/v1/organizations/enrich"
            f"?domain={domain}"
        )

        try:
            # Попытка через публичный API (без ключа — может вернуть ограниченные данные)
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    api_url,
                    headers={
                        "Content-Type": "application/json",
                        "Cache-Control": "no-cache",
                    },
                )
                if resp.status_code == 200:
                    raw = resp.json()
                    org = raw.get("organization", {})
                    if org:
                        return CollectorResult(
                            source_name=self.source_name,
                            status="success",
                            data=self._normalize_api(org),
                            retrieved_at=datetime.now(timezone.utc),
                            url_used=api_url,
                            confidence=0.85,
                        )
        except Exception as exc:
            self.logger.debug(f"Apollo API failed: {exc}")

        # Fallback: скрапинг публичной страницы
        try:
            public_url = f"https://www.apollo.io/companies/{search_query}"
            html = await self.proxy.get_html(public_url, residential=True, render_js=True)
            data = self._parse_html(html, search_query)
            return CollectorResult(
                source_name=self.source_name,
                status="partial" if data else "failed",
                data=data or {"note": "Could not extract Apollo data"},
                retrieved_at=datetime.now(timezone.utc),
                url_used=public_url,
                confidence=0.5 if data else 0.0,
            )
        except Exception as exc:
            return make_failed_result(self.source_name, search_url, str(exc))

    def _normalize_api(self, org: dict) -> dict:
        return {
            "name": org.get("name", ""),
            "domain": org.get("primary_domain", ""),
            "industry": org.get("industry", ""),
            "employee_count": org.get("estimated_num_employees", 0),
            "employee_range": org.get("employee_count", ""),
            "annual_revenue": org.get("annual_revenue_printed", ""),
            "technologies": org.get("technologies", [])[:10],
            "linkedin_url": org.get("linkedin_url", ""),
            "phone": org.get("phone", ""),
            "city": org.get("city", ""),
            "country": org.get("country", ""),
            "keywords": org.get("keywords", [])[:10],
            "sic_codes": org.get("sic_codes", []),
        }

    def _parse_html(self, html: str, query: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ")
        data: dict = {"query": query}

        m = re.search(r"(\d[\d,]*)\s*employee", text, re.I)
        if m:
            data["employee_count"] = m.group(1).replace(",", "")

        m2 = re.search(r"(\$[\d.,]+[MBK]?)\s*(?:in\s+)?revenue", text, re.I)
        if m2:
            data["revenue_estimate"] = m2.group(1)

        return data if len(data) > 1 else {}
