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

        # Proxy fallback
        try:
            html = await self.proxy.get_html(
                profile_url, residential=True, render_js=True
            )
            data = self._parse_html(html)
            if not data.get("name"):
                return make_failed_result(
                    self.source_name, profile_url, "Could not parse profile"
                )
            return CollectorResult(
                source_name=self.source_name,
                status="partial",
                data=data,
                retrieved_at=datetime.now(timezone.utc),
                url_used=profile_url,
                confidence=0.65,
            )
        except Exception as exc:
            return make_failed_result(self.source_name, profile_url, str(exc))

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
