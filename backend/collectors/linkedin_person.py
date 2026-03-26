"""
LinkedInPersonCollector — профиль ЛПР (лица, принимающего решения).

Требует linkedin_lpr_url в context — если не передан, возвращает not_applicable.
Использует ScrapeOps Parser API (linkedin-profile) или Proxy + BS4.

Извлекает: имя, должность, компания, опыт, активность, тип профиля.
"""
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from collectors.base import (
    BaseCollector, CollectorResult,
    make_failed_result, make_not_applicable_result,
)
from scrapeops.proxy_client import ScrapeOpsProxyClient
from scrapeops.parser_client import ScrapeOpsParserClient


class LinkedInPersonCollector(BaseCollector):
    source_name = "linkedin_person"

    def __init__(self):
        super().__init__()
        self.proxy = ScrapeOpsProxyClient()
        self.parser = ScrapeOpsParserClient()

    async def collect(self, context: dict) -> CollectorResult:
        profile_url = context.get("linkedin_lpr_url")
        if not profile_url:
            return make_not_applicable_result(
                self.source_name, "linkedin_lpr_url not provided"
            )

        # Parser API
        try:
            raw = await self.parser.extract_linkedin_profile(profile_url)
            if raw and raw.get("full_name"):
                return CollectorResult(
                    source_name=self.source_name,
                    status="success",
                    data=self._normalize(raw),
                    retrieved_at=datetime.now(timezone.utc),
                    url_used=profile_url,
                    confidence=0.9,
                )
        except Exception as exc:
            self.logger.debug(f"Parser API failed: {exc}")

        # Fallback 2: прямой httpx (без прокси — LinkedIn может заблокировать,
        # но иногда возвращает публичные данные)
        try:
            import httpx
            async with httpx.AsyncClient(
                timeout=20,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/123.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                },
            ) as client:
                resp = await client.get(profile_url)
                if resp.status_code == 200:
                    data = self._parse_html(resp.text)
                    if data.get("name"):
                        return CollectorResult(
                            source_name=self.source_name,
                            status="partial",
                            data=data,
                            retrieved_at=datetime.now(timezone.utc),
                            url_used=profile_url,
                            confidence=0.5,
                        )
        except Exception as exc:
            self.logger.debug(f"Direct httpx for LinkedIn failed: {exc}")

        # Fallback 3: извлекаем имя из URL и собираем публичные данные через DDG
        name_from_url = self._extract_name_from_linkedin_url(profile_url)
        if name_from_url:
            try:
                duckduckgo_data = await self._search_person_ddg(name_from_url, profile_url)
                if duckduckgo_data:
                    return CollectorResult(
                        source_name=self.source_name,
                        status="partial",
                        data=duckduckgo_data,
                        retrieved_at=datetime.now(timezone.utc),
                        url_used=profile_url,
                        confidence=0.4,
                        error_message="Data from public search, not direct LinkedIn scrape",
                    )
            except Exception as exc:
                self.logger.debug(f"DDG person search failed: {exc}")

        return make_failed_result(self.source_name, profile_url, "All scraping methods failed")

    def _normalize(self, raw: dict) -> dict:
        experiences = raw.get("experiences", [])
        current_exp = experiences[0] if experiences else {}
        posts = raw.get("posts", [])
        return {
            "name": raw.get("full_name", ""),
            "headline": raw.get("headline", ""),
            "current_title": current_exp.get("title", raw.get("current_position", "")),
            "current_company": current_exp.get("company", ""),
            "location": raw.get("location", ""),
            "connections": raw.get("connections", 0),
            "followers": raw.get("followers", 0),
            "about": raw.get("summary", "")[:500],
            "experience": experiences[:5],
            "education": raw.get("education", [])[:3],
            "skills": raw.get("skills", [])[:10],
            "recent_posts": [
                {"text": p.get("text", "")[:200], "likes": p.get("likes", 0)}
                for p in posts[:3]
            ],
            "posts_per_month_estimate": len(posts),
            "profile_type": self._classify_profile(raw),
        }

    def _classify_profile(self, raw: dict) -> str:
        """
        Определяет тип ЛПР: creator | quiet_pro | networker | newcomer
        на основе активности профиля.
        """
        posts = raw.get("posts", [])
        connections = raw.get("connections", 0)
        followers = raw.get("followers", 0)

        if len(posts) >= 4 and followers > 500:
            return "creator"
        if connections > 1000 and len(posts) < 2:
            return "networker"
        exp = raw.get("experiences", [])
        if exp and len(exp) <= 1:
            return "newcomer"
        return "quiet_pro"

    def _extract_name_from_linkedin_url(self, url: str) -> str:
        """
        Извлекает читаемое имя из LinkedIn URL.
        Пример: linkedin.com/in/david-mcginnis-a7b6b283 → "David McGinnis"
        """
        try:
            # Достаём slug из /in/SLUG
            slug = url.rstrip("/").split("/in/")[-1].split("?")[0]
            # Убираем числовой суффикс (идентификатор типа -a7b6b283)
            parts = slug.split("-")
            # Числовой суффикс — последний сегмент если он короткий и содержит цифры
            if parts and len(parts[-1]) <= 10 and any(c.isdigit() for c in parts[-1]):
                parts = parts[:-1]
            # Капитализируем каждое слово
            name = " ".join(p.capitalize() for p in parts if p)
            return name if len(name) > 3 else ""
        except Exception:
            return ""

    async def _search_person_ddg(self, name: str, linkedin_url: str) -> dict:
        """
        Ищет публичные данные о человеке через DuckDuckGo.
        Используется когда прямой скрапинг LinkedIn невозможен.
        """
        try:
            from duckduckgo_search import DDGS
            from config import settings

            # Определяем прокси
            proxy = settings.scrapeops_http_proxy if settings.scrapeops_api_key else None

            ddgs_kwargs: dict = {}
            if proxy:
                ddgs_kwargs["proxy"] = proxy

            queries = {
                "profile": f'"{name}" LinkedIn CEO OR founder OR director',
                "background": f'"{name}" company OR career OR background',
            }

            search_results: dict = {}
            with DDGS(**ddgs_kwargs) as ddgs:
                for category, query in queries.items():
                    try:
                        hits = list(ddgs.text(query, max_results=5))
                        search_results[category] = [
                            {"title": h.get("title", ""), "snippet": h.get("body", "")}
                            for h in hits
                        ]
                    except Exception:
                        search_results[category] = []

            # Формируем базовый профиль
            return {
                "name": name,
                "headline": "",
                "current_title": "",
                "current_company": "",
                "location": "",
                "connections": 0,
                "followers": 0,
                "about": "",
                "experience": [],
                "education": [],
                "skills": [],
                "recent_posts": [],
                "posts_per_month_estimate": 0,
                "profile_type": "quiet_pro",
                "search_snippets": search_results,  # передаём в LLM для извлечения данных
                "linkedin_url": linkedin_url,
            }
        except Exception:
            return {}

    def _parse_html(self, html: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        data: dict = {}
        h1 = soup.find("h1")
        if h1:
            data["name"] = h1.get_text(strip=True)
        headline = soup.find(
            "div", {"class": re.compile(r"headline|title", re.I)}
        )
        if headline:
            data["headline"] = headline.get_text(strip=True)[:200]
        return data
