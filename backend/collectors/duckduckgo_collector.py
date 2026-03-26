"""
SearchCollector (duckduckgo_collector) — поиск публичной информации о компании.

Бэкенды по приоритету:
1. Serper.dev  — Google результаты через API, нет рейтлимита (POST /search)
2. DDGS proxy  — DuckDuckGo через ScrapeOps HTTP proxy (если ключ рабочий)
3. DDGS direct — DuckDuckGo прямой с задержками (бесплатный fallback)

Данные возвращаются плоской структурой: news, key_people, competitors, etc.
на верхнем уровне data — чтобы analyst._aggregate_by_block видел
duckduckgo__news, duckduckgo__key_people и т.д. напрямую.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from collectors.base import BaseCollector, CollectorResult, make_failed_result
from config import settings

logger = logging.getLogger(__name__)

MAX_RESULTS = 10
DDG_INTER_QUERY_DELAY = 3.0  # секунд между запросами при прямом DDG


class DuckDuckGoCollector(BaseCollector):
    source_name = "duckduckgo"

    async def collect(self, context: dict) -> CollectorResult:
        website_url = context.get("website_url", "")
        company_name = context.get("company_name") or context.get("resolved_company_name", "")
        domain = self.extract_domain(website_url) if website_url else ""

        query_base = company_name or domain
        if not query_base:
            return make_failed_result(self.source_name, "", "No company_name or domain to search")

        queries: dict[str, str] = {
            "news":         f'"{query_base}" news OR press OR announcement OR launch',
            "key_people":   (
                f'"{query_base}" CEO OR founder OR "co-founder" OR director '
                f'OR owner OR president OR VP'
            ),
            "competitors":  f'"{query_base}" competitors OR "vs " OR "alternative to"',
            "reviews":      f'"{query_base}" reviews OR testimonials OR rating',
            "funding":      f'"{query_base}" revenue OR funding OR employees OR "annual revenue"',
            "jobs":         f'"{query_base}" hiring OR jobs OR careers',
            "market_context": f'{query_base} industry market size OR trends OR growth',
        }

        if context.get("linkedin_lpr_url"):
            queries["lpr_info"] = f'"{context["linkedin_lpr_url"]}"'
        elif query_base:
            queries["lpr_linkedin"] = (
                f'"{query_base}" CEO OR founder OR director site:linkedin.com/in'
            )

        results = await self._search(queries, query_base)

        has_data = any(len(v) > 0 for v in results.values())
        total = sum(len(v) for v in results.values())

        return CollectorResult(
            source_name=self.source_name,
            status="success" if has_data else "partial",
            data={
                "company_query": query_base,
                "total_results_found": total,
                "search_backend": results.pop("_backend", "unknown"),
                **results,
            },
            retrieved_at=datetime.now(timezone.utc),
            url_used=f"https://google.serper.dev/search?q={query_base}",
            confidence=0.7 if has_data else 0.1,
            error_message=None if has_data else "No results found",
        )

    # ── Выбор бэкенда ────────────────────────────────────────────────────

    async def _search(self, queries: dict, query_base: str) -> dict[str, list]:
        # 1. Serper.dev
        if settings.serper_api_key:
            try:
                results = await self._search_serper(queries)
                if any(len(v) > 0 for v in results.values()):
                    logger.info(f"[search] '{query_base}' via Serper.dev: {sum(len(v) for v in results.values())} hits")
                    results["_backend"] = "serper"
                    return results
                logger.warning(f"[search] Serper returned 0 results for '{query_base}'")
            except Exception as exc:
                logger.warning(f"[search] Serper failed: {exc}")

        # 2. DDGS через ScrapeOps proxy
        if settings.scrapeops_api_key:
            try:
                proxy = settings.scrapeops_http_proxy
                results = await self._search_ddgs(queries, proxy=proxy)
                if any(len(v) > 0 for v in results.values()):
                    logger.info(f"[search] '{query_base}' via DDG+ScrapeOps proxy")
                    results["_backend"] = "ddgs_proxy"
                    return results
            except Exception as exc:
                logger.debug(f"[search] DDG+proxy failed: {exc}")

        # 3. DDGS прямой с задержками
        try:
            results = await self._search_ddgs(queries, proxy=None, with_delay=True)
            logger.info(f"[search] '{query_base}' via direct DDG (with delays)")
            results["_backend"] = "ddgs_direct"
            return results
        except Exception as exc:
            logger.warning(f"[search] All backends failed for '{query_base}': {exc}")
            return {k: [] for k in queries}

    # ── Serper.dev ────────────────────────────────────────────────────────

    async def _search_serper(self, queries: dict) -> dict[str, list]:
        """
        POST https://google.serper.dev/search
        Headers: X-API-KEY, Content-Type: application/json
        Body: {"q": "...", "num": 10, "gl": "us", "hl": "en"}
        Response: {"organic": [{"title", "link", "snippet"}, ...]}
        """
        results: dict[str, list] = {}

        async with httpx.AsyncClient(timeout=20) as client:
            for category, query in queries.items():
                if category == "_backend":
                    continue
                try:
                    resp = await client.post(
                        "https://google.serper.dev/search",
                        headers={
                            "X-API-KEY": settings.serper_api_key,
                            "Content-Type": "application/json",
                        },
                        json={
                            "q": query,
                            "num": MAX_RESULTS,
                            "gl": "us",
                            "hl": "en",
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    hits = data.get("organic", [])
                    # Serper также возвращает "answerBox", "knowledgeGraph" — берём organic
                    results[category] = [
                        {
                            "title":   h.get("title", ""),
                            "url":     h.get("link", ""),
                            "snippet": h.get("snippet", ""),
                        }
                        for h in hits[:MAX_RESULTS]
                    ]
                except Exception as exc:
                    logger.debug(f"[serper] query '{category}' failed: {exc}")
                    results[category] = []

        return results

    # ── DDGS fallback ─────────────────────────────────────────────────────

    async def _search_ddgs(
        self,
        queries: dict,
        proxy: str | None = None,
        with_delay: bool = False,
    ) -> dict[str, list]:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            raise RuntimeError("duckduckgo-search not installed")

        results: dict[str, list] = {}
        ddgs_kwargs: dict[str, Any] = {}
        if proxy:
            ddgs_kwargs["proxy"] = proxy

        with DDGS(**ddgs_kwargs) as ddgs:
            for i, (category, query) in enumerate(queries.items()):
                if category == "_backend":
                    continue
                if with_delay and i > 0:
                    await asyncio.sleep(DDG_INTER_QUERY_DELAY)
                try:
                    hits = list(ddgs.text(query, max_results=MAX_RESULTS))
                    results[category] = [
                        {
                            "title":   h.get("title", ""),
                            "url":     h.get("href", ""),
                            "snippet": h.get("body", ""),
                        }
                        for h in hits
                    ]
                except Exception as exc:
                    logger.warning(f"[ddgs] query '{category}' failed: {exc}")
                    results[category] = []

        return results
