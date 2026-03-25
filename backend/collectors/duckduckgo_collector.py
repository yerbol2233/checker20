"""
DuckDuckGoCollector — поиск публичной информации о компании.

Использует duckduckgo-search (Python lib, без API ключа).
Собирает:
- топ-10 результатов по запросу "{company} site:news"
- упоминания в прессе
- результаты по "{company} reviews"
- результаты по "{company} funding"
"""
import logging
from datetime import datetime, timezone
from typing import Any

from collectors.base import BaseCollector, CollectorResult, make_failed_result

logger = logging.getLogger(__name__)

MAX_RESULTS = 10


class DuckDuckGoCollector(BaseCollector):
    source_name = "duckduckgo"

    async def collect(self, context: dict) -> CollectorResult:
        website_url = context.get("website_url", "")
        company_name = context.get("company_name") or context.get("resolved_company_name", "")
        domain = self.extract_domain(website_url) if website_url else ""

        # Формируем поисковый запрос
        query_base = company_name or domain
        if not query_base:
            return make_failed_result(
                self.source_name, "", "No company_name or domain to search"
            )

        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return make_failed_result(
                self.source_name, "",
                "duckduckgo-search not installed"
            )

        results: dict[str, Any] = {}

        queries = {
            "news": f'"{query_base}" news OR press OR announcement',
            "reviews": f'"{query_base}" reviews OR customers',
            "funding": f'"{query_base}" funding OR investment OR raised',
            "jobs": f'"{query_base}" hiring OR jobs OR careers',
        }

        try:
            with DDGS() as ddgs:
                for category, query in queries.items():
                    try:
                        hits = list(ddgs.text(query, max_results=MAX_RESULTS))
                        results[category] = [
                            {
                                "title": h.get("title", ""),
                                "url": h.get("href", ""),
                                "snippet": h.get("body", ""),
                            }
                            for h in hits
                        ]
                    except Exception as exc:
                        self.logger.warning(
                            f"DuckDuckGo query '{category}' failed: {exc}"
                        )
                        results[category] = []
        except Exception as exc:
            return make_failed_result(
                self.source_name, f"ddg:{query_base}",
                f"DuckDuckGo search failed: {exc}"
            )

        has_data = any(len(v) > 0 for v in results.values())
        total_results = sum(len(v) for v in results.values())

        return CollectorResult(
            source_name=self.source_name,
            status="success" if has_data else "partial",
            data={
                "company_query": query_base,
                "results": results,
                "total_results_found": total_results,
            },
            retrieved_at=datetime.now(timezone.utc),
            url_used=f"https://duckduckgo.com/?q={query_base}",
            confidence=0.6 if has_data else 0.1,
            error_message=None if has_data else "No results found",
        )
