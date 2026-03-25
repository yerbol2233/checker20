"""
IndeedCollector — вакансии и отзывы сотрудников на Indeed.

Использует ScrapeOps Proxy + BS4 (по примеру scrapeops-scrapers/indeed).
Извлекает: рейтинг работодателя, кол-во вакансий, активные позиции SDR/Sales,
отзывы сотрудников.
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


class IndeedCollector(BaseCollector):
    source_name = "indeed"

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

        # Indeed company reviews
        slug = re.sub(r"[^a-z0-9-]", "-", company_name.lower()).strip("-")
        company_url = f"https://www.indeed.com/cmp/{slug}/reviews"
        # Jobs search
        jobs_url = (
            f"https://www.indeed.com/jobs"
            f"?q={quote_plus('SDR OR sales representative')}"
            f"&sc=0kf%3Acmp({quote_plus(company_name)})%3B"
        )

        data: dict = {}
        try:
            html = await self.proxy.get_html(
                company_url, residential=True, render_js=False
            )
            data.update(self._parse_reviews(html, company_url))
        except Exception as exc:
            self.logger.debug(f"Reviews page failed: {exc}")

        try:
            html2 = await self.proxy.get_html(
                jobs_url, residential=False, render_js=False
            )
            data.update(self._parse_jobs(html2))
        except Exception as exc:
            self.logger.debug(f"Jobs page failed: {exc}")

        return CollectorResult(
            source_name=self.source_name,
            status="success" if data.get("employer_rating") or data.get("open_jobs_count") else "partial",
            data=data,
            retrieved_at=datetime.now(timezone.utc),
            url_used=company_url,
            confidence=0.75 if data.get("employer_rating") else 0.3,
        )

    def _parse_reviews(self, html: str, url: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ")
        data: dict = {"reviews_url": url}

        m = re.search(r"(\d+\.?\d*)\s*out of\s*5", text, re.I)
        if m:
            data["employer_rating"] = float(m.group(1))

        m2 = re.search(r"([\d,]+)\s+review", text, re.I)
        if m2:
            data["reviews_count"] = int(m2.group(1).replace(",", ""))

        # Pros/Cons
        pros, cons = [], []
        for el in soup.find_all(attrs={"itemprop": "reviewBody"})[:6]:
            txt = el.get_text(strip=True)[:200]
            if txt:
                pros.append(txt)
        data["review_snippets"] = pros

        # Рекомендуют ли работодателя
        m3 = re.search(r"(\d+)\s*%\s*(?:of employees\s*)?recommend", text, re.I)
        if m3:
            data["recommend_pct"] = int(m3.group(1))

        return data

    def _parse_jobs(self, html: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ")
        data: dict = {}

        m = re.search(r"([\d,]+)\s+job", text, re.I)
        if m:
            data["open_jobs_count"] = int(m.group(1).replace(",", ""))

        # Заголовки вакансий
        titles = []
        for el in soup.find_all(attrs={"data-jk": True})[:5]:
            title_el = el.find(["h2", "h3", "span"])
            if title_el:
                titles.append(title_el.get_text(strip=True))
        data["job_titles"] = titles

        return data
