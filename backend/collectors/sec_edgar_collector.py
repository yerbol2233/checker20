"""
SECEdgarCollector — финансовые отчёты публичных компаний (SEC EDGAR).

Использует публичный EDGAR Full-Text Search API (без ключа).
Применимо только для публичных компаний США.

Извлекает: последние 10-K/10-Q/8-K файлы, упоминания revenue,
выручки, рисков, изменений в менеджменте.
"""
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

import httpx

from collectors.base import (
    BaseCollector, CollectorResult,
    make_failed_result, make_not_applicable_result,
)

EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index?q={query}&dateRange=custom&startdt=2023-01-01&forms=10-K,10-Q,8-K"
EDGAR_API_URL = "https://data.sec.gov/submissions/"
HEADERS = {"User-Agent": "CIA-System research@example.com"}


class SECEdgarCollector(BaseCollector):
    source_name = "sec_edgar"

    async def collect(self, context: dict) -> CollectorResult:
        company_name = (
            context.get("company_name")
            or context.get("resolved_company_name", "")
        )
        if not company_name:
            return make_not_applicable_result(self.source_name, "No company name")

        search_url = (
            f"https://efts.sec.gov/LATEST/search-index"
            f"?q={quote_plus(company_name)}"
            f"&forms=10-K,10-Q,8-K"
        )

        try:
            async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
                resp = await client.get(search_url)
                resp.raise_for_status()
                raw = resp.json()
        except Exception as exc:
            # EDGAR недоступен или компания не публичная
            return CollectorResult(
                source_name=self.source_name,
                status="not_applicable",
                data={"note": "Company likely not public or SEC search failed"},
                retrieved_at=datetime.now(timezone.utc),
                url_used=search_url,
                confidence=0.0,
                error_message=str(exc),
            )

        hits = raw.get("hits", {}).get("hits", [])
        if not hits:
            return CollectorResult(
                source_name=self.source_name,
                status="not_applicable",
                data={"note": "Not found in SEC EDGAR — likely private company"},
                retrieved_at=datetime.now(timezone.utc),
                url_used=search_url,
                confidence=0.0,
            )

        filings = []
        for hit in hits[:5]:
            src = hit.get("_source", {})
            filings.append({
                "form_type": src.get("form_type", ""),
                "filed_at": src.get("file_date", ""),
                "company_name": src.get("entity_name", ""),
                "description": src.get("period_of_report", ""),
                "url": f"https://www.sec.gov/Archives/edgar/data/{src.get('entity_id', '')}/",
            })

        return CollectorResult(
            source_name=self.source_name,
            status="success",
            data={
                "company_name": company_name,
                "filings_found": len(hits),
                "recent_filings": filings,
                "is_public": True,
            },
            retrieved_at=datetime.now(timezone.utc),
            url_used=search_url,
            confidence=0.95,
        )
