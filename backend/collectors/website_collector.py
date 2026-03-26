"""
WebsiteCollector — скрапинг сайта компании.

Извлекает:
- title, description, keywords
- текст главной страницы (очищенный)
- ссылки на /about, /pricing, /careers, /blog
- наличие чат-бота, форм, CTA
- тексты со страниц /about и /pricing
"""
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from collectors.base import BaseCollector, CollectorResult, make_failed_result
from scrapeops.proxy_client import ScrapeOpsProxyClient

logger = logging.getLogger(__name__)

IMPORTANT_PAGES = ["/about", "/about-us", "/pricing", "/price", "/careers", "/jobs"]
MAX_TEXT_LENGTH = 5000


class WebsiteCollector(BaseCollector):
    source_name = "website"

    def __init__(self):
        super().__init__()
        self.proxy = ScrapeOpsProxyClient()

    async def collect(self, context: dict) -> CollectorResult:
        url = context.get("website_url", "")
        if not url:
            return make_failed_result(self.source_name, "", "No website_url provided")

        # Нормализуем URL
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            html = await self.proxy.get_html(url, render_js=False)
        except Exception as exc:
            self.logger.warning(f"Failed to fetch {url}: {exc}")
            # Пробуем без прокси как fallback
            try:
                import httpx
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        url,
                        headers={
                            "User-Agent": (
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36"
                            )
                        },
                        follow_redirects=True,
                    )
                    resp.raise_for_status()
                    html = resp.text
            except Exception as exc2:
                return make_failed_result(
                    self.source_name, url,
                    f"Fetch failed (proxy+direct): {exc2}"
                )

        data = self._parse_homepage(html, url)

        # Пробуем собрать дополнительные страницы
        sub_pages = await self._collect_sub_pages(url)
        data.update(sub_pages)

        return CollectorResult(
            source_name=self.source_name,
            status="success" if data.get("title") else "partial",
            data=data,
            retrieved_at=datetime.now(timezone.utc),
            url_used=url,
            confidence=0.9 if data.get("title") else 0.5,
            error_message=None,
        )

    def _parse_homepage(self, html: str, base_url: str) -> dict:
        soup = BeautifulSoup(html, "lxml")

        # Мета-данные
        title = soup.title.string.strip() if soup.title else ""
        description = ""
        keywords = ""
        meta_desc = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
        meta_kw = soup.find("meta", attrs={"name": re.compile(r"keywords", re.I)})
        if meta_desc:
            description = meta_desc.get("content", "")
        if meta_kw:
            keywords = meta_kw.get("content", "")

        # Основной текст (убираем nav/footer/script/style)
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()
        text = text[:MAX_TEXT_LENGTH]

        # Ключевые ссылки + LinkedIn/Twitter URLs из всех тегов <a>
        links = {}
        linkedin_company_url = ""
        twitter_url = ""

        for a in soup.find_all("a", href=True):
            href = a["href"]
            href_lower = href.lower()
            full = urljoin(base_url, href)

            for page in IMPORTANT_PAGES:
                if page in href_lower and page not in links:
                    links[page] = full

            # Ищем LinkedIn страницу компании
            if not linkedin_company_url and "linkedin.com/company/" in href_lower:
                clean = href.split("?")[0].rstrip("/")
                if clean.startswith("http"):
                    linkedin_company_url = clean
                else:
                    linkedin_company_url = "https://www.linkedin.com/company/" + \
                        href_lower.split("linkedin.com/company/")[-1].split("/")[0]

            # Ищем Twitter/X профиль компании
            if not twitter_url and (
                "twitter.com/" in href_lower or "x.com/" in href_lower
            ):
                if "/intent/" not in href_lower and "/share" not in href_lower:
                    twitter_url = href.split("?")[0].rstrip("/")

        # Наличие признаков
        html_lower = html.lower()
        has_chat = any(
            kw in html_lower
            for kw in ["intercom", "drift", "hubspot", "crisp", "zendesk", "tawk"]
        )
        has_pricing = bool(links.get("/pricing") or links.get("/price"))
        has_careers = bool(links.get("/careers") or links.get("/jobs"))

        result = {
            "title": title,
            "meta_description": description,
            "meta_keywords": keywords,
            "homepage_text": text,
            "important_links": links,
            "has_live_chat": has_chat,
            "has_pricing_page": has_pricing,
            "has_careers_page": has_careers,
        }
        if linkedin_company_url:
            result["linkedin_company_url"] = linkedin_company_url
        if twitter_url:
            result["twitter_url"] = twitter_url
        return result

    async def _collect_sub_pages(self, base_url: str) -> dict:
        """Пробует скачать /about и /pricing для дополнительного контекста."""
        sub_data = {}
        domain = base_url.rstrip("/")

        for slug in ["/about", "/about-us", "/pricing"]:
            target = domain + slug
            try:
                html = await self.proxy.get_html(target, render_js=False)
                soup = BeautifulSoup(html, "lxml")
                for tag in soup(["script", "style", "nav", "footer"]):
                    tag.decompose()
                text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()
                text = text[:2000]
                if text:
                    key = slug.lstrip("/").replace("-", "_") + "_text"
                    sub_data[key] = text
                    break  # нашли /about — не пробуем /about-us
            except Exception:
                continue

        return sub_data
