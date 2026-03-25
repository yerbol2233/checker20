"""
CrunchbaseCollector — инвестиции, раунды финансирования, инвесторы.

Использует ScrapeOps Proxy + BS4 для скрапинга публичных страниц Crunchbase.
Извлекает: раунды, суммы, инвесторов, статус компании, описание.
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


class CrunchbaseCollector(BaseCollector):
    source_name = "crunchbase"

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

        # Строим URL страницы организации
        slug = re.sub(r"[^a-z0-9-]", "-", query.lower()).strip("-")
        org_url = f"https://www.crunchbase.com/organization/{slug}"

        try:
            html = await self.proxy.get_html(
                org_url, residential=True, render_js=True
            )
            data = self._parse(html, org_url)
            if not data.get("name") and not data.get("funding_rounds"):
                # Попробуем поиск
                search_url = (
                    f"https://www.crunchbase.com/textsearch"
                    f"?q={quote_plus(query)}"
                )
                html2 = await self.proxy.get_html(
                    search_url, residential=True, render_js=True
                )
                data = self._parse_search(html2, query)

            return CollectorResult(
                source_name=self.source_name,
                status="success" if data.get("funding_total") else "partial",
                data=data,
                retrieved_at=datetime.now(timezone.utc),
                url_used=org_url,
                confidence=0.75 if data.get("funding_total") else 0.4,
            )
        except Exception as exc:
            return make_failed_result(self.source_name, org_url, str(exc))

    def _parse(self, html: str, url: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        data: dict = {"url": url}

        # Название
        h1 = soup.find("h1")
        if h1:
            data["name"] = h1.get_text(strip=True)

        # Описание
        desc = soup.find("p", {"class": re.compile(r"description|short-description", re.I)})
        if desc:
            data["description"] = desc.get_text(strip=True)[:500]

        # Поиск финансовых данных в тексте страницы
        text = soup.get_text(" ")
        # Total funding
        m = re.search(
            r"total\s+funding[:\s]+\$?([\d.,]+\s*[MBKmkb]?)", text, re.I
        )
        if m:
            data["funding_total"] = m.group(1).strip()

        # Последний раунд
        m2 = re.search(
            r"(Series [A-F]|Seed|Pre-Seed|Series A|Series B|Series C|IPO|Debt Financing)",
            text,
        )
        if m2:
            data["last_round_type"] = m2.group(1)

        # Основатели
        founders_section = soup.find(
            string=re.compile(r"founder|co-founder", re.I)
        )
        if founders_section:
            data["has_founders_info"] = True

        # Год основания
        m3 = re.search(r"Founded\s+(\d{4})", text)
        if m3:
            data["founded_year"] = m3.group(1)

        # Количество сотрудников
        m4 = re.search(r"(\d[\d,]*)\s*employee", text, re.I)
        if m4:
            data["employees"] = m4.group(1).replace(",", "")

        return data

    def _parse_search(self, html: str, query: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        links = soup.find_all("a", href=re.compile(r"/organization/"))
        if links:
            return {
                "query": query,
                "possible_url": "https://www.crunchbase.com" + links[0]["href"],
            }
        return {"query": query}
