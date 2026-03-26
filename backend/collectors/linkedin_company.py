"""
LinkedInCompanyCollector — данные страницы компании LinkedIn.

Использует ScrapeOps Parser API (парсер linkedin-company) или
Proxy API + BeautifulSoup как fallback.

Извлекает: название, размер, отрасль, описание, кол-во подписчиков,
посты в месяц, основатели, сотрудники.
"""
import re
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

from collectors.base import (
    BaseCollector, CollectorResult,
    make_failed_result, make_not_applicable_result,
)
from scrapeops.proxy_client import ScrapeOpsProxyClient
from scrapeops.parser_client import ScrapeOpsParserClient


class LinkedInCompanyCollector(BaseCollector):
    source_name = "linkedin_company"

    def __init__(self):
        super().__init__()
        self.proxy = ScrapeOpsProxyClient()
        self.parser = ScrapeOpsParserClient()

    async def collect(self, context: dict) -> CollectorResult:
        website_url = context.get("website_url", "")
        company_name = context.get("company_name") or context.get("resolved_company_name", "")
        domain = self.extract_domain(website_url) if website_url else ""

        if not company_name and not domain:
            return make_not_applicable_result(self.source_name, "No company_name or domain")

        # Приоритет: URL найденный на сайте > строим по имени/домену
        found_url = context.get("linkedin_company_url")

        # Генерируем несколько вариантов слагов (разные форматы имён)
        candidate_urls = []
        if found_url:
            candidate_urls.append(found_url)
        if company_name:
            candidate_urls.append(self._build_linkedin_url(company_name))
            # Вариант без стоп-слов (LLC, Inc, Ltd, Corp)
            clean_name = re.sub(
                r"\b(llc|inc|ltd|corp|co|company|group|services|solutions)\b",
                "", company_name, flags=re.I
            ).strip()
            if clean_name and clean_name != company_name:
                candidate_urls.append(self._build_linkedin_url(clean_name))
        if domain:
            candidate_urls.append(self._build_linkedin_url(domain.split(".")[0]))

        # Убираем дубликаты, сохраняя порядок
        seen: set = set()
        unique_urls = []
        for u in candidate_urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        # Пробуем каждый кандидат через Parser API
        last_exc = None
        for linkedin_url in unique_urls:
            try:
                data = await self.parser.extract_linkedin_company(linkedin_url)
                if data and data.get("name"):
                    return CollectorResult(
                        source_name=self.source_name,
                        status="success",
                        data=self._normalize_parser_data(data),
                        retrieved_at=datetime.now(timezone.utc),
                        url_used=linkedin_url,
                        confidence=0.85,
                    )
            except Exception as exc:
                last_exc = exc
                self.logger.debug(f"Parser API failed for {linkedin_url}: {exc}")

        # Fallback: Proxy + BS4 для первого кандидата
        primary_url = unique_urls[0] if unique_urls else self._build_linkedin_url(company_name or domain)
        try:
            html = await self.proxy.get_html(
                primary_url, residential=True, render_js=True
            )
            data = self._parse_html(html)
            if not data:
                return make_failed_result(self.source_name, primary_url, "Could not parse LinkedIn page")
            return CollectorResult(
                source_name=self.source_name,
                status="partial",
                data=data,
                retrieved_at=datetime.now(timezone.utc),
                url_used=primary_url,
                confidence=0.6,
            )
        except Exception as exc:
            return make_failed_result(self.source_name, primary_url, str(exc))

    def _build_linkedin_url(self, company_slug: str) -> str:
        slug = re.sub(r"[^a-z0-9-]", "-", company_slug.lower()).strip("-")
        # Убираем повторяющиеся дефисы
        slug = re.sub(r"-{2,}", "-", slug)
        return f"https://www.linkedin.com/company/{slug}/"

    def _normalize_parser_data(self, raw: dict) -> dict:
        return {
            "name": raw.get("name", ""),
            "description": raw.get("description", ""),
            "industry": raw.get("industry", ""),
            "company_size": raw.get("company_size", ""),
            "headquarters": raw.get("headquarters", ""),
            "founded": raw.get("founded", ""),
            "followers": raw.get("followers_count", 0),
            "website": raw.get("website", ""),
            "specialties": raw.get("specialties", []),
            "type": raw.get("company_type", ""),
        }

    def _parse_html(self, html: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        data: dict = {}
        # Название
        h1 = soup.find("h1")
        if h1:
            data["name"] = h1.get_text(strip=True)
        # Описание
        desc = soup.find("p", {"class": re.compile(r"description|about", re.I)})
        if desc:
            data["description"] = desc.get_text(strip=True)[:1000]
        # Размер / отрасль из dl/dt/dd блоков
        for dt in soup.find_all("dt"):
            label = dt.get_text(strip=True).lower()
            dd = dt.find_next_sibling("dd")
            if not dd:
                continue
            val = dd.get_text(strip=True)
            if "size" in label or "employee" in label:
                data["company_size"] = val
            elif "industry" in label:
                data["industry"] = val
            elif "headquarter" in label:
                data["headquarters"] = val
            elif "founded" in label:
                data["founded"] = val
        return data
