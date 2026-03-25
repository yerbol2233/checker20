"""
RedditCollector — упоминания компании на Reddit.

Использует публичный Reddit JSON API (без ключа).
Извлекает: обсуждения о компании, жалобы, позитивные упоминания,
упоминания в контексте продаж/CRM.
"""
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

import httpx

from collectors.base import (
    BaseCollector, CollectorResult,
    make_failed_result, make_not_applicable_result,
)

REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"
REDDIT_HEADERS = {
    "User-Agent": "CIA-System/1.0 (research tool; contact@example.com)",
}


class RedditCollector(BaseCollector):
    source_name = "reddit"

    async def collect(self, context: dict) -> CollectorResult:
        company_name = (
            context.get("company_name")
            or context.get("resolved_company_name", "")
        )
        domain = self.extract_domain(context.get("website_url", ""))
        query = company_name or domain
        if not query:
            return make_not_applicable_result(self.source_name, "No company name")

        params = {
            "q": query,
            "sort": "relevance",
            "t": "year",
            "limit": 15,
            "type": "link",
        }

        search_url = REDDIT_SEARCH_URL + "?" + "&".join(f"{k}={quote_plus(str(v))}" for k, v in params.items())

        try:
            async with httpx.AsyncClient(
                timeout=15,
                headers=REDDIT_HEADERS,
                follow_redirects=True,
            ) as client:
                resp = await client.get(search_url)
                resp.raise_for_status()
                raw = resp.json()
        except Exception as exc:
            return make_failed_result(self.source_name, search_url, str(exc))

        posts_data = raw.get("data", {}).get("children", [])
        if not posts_data:
            return CollectorResult(
                source_name=self.source_name,
                status="partial",
                data={"query": query, "posts": [], "note": "No Reddit mentions found"},
                retrieved_at=datetime.now(timezone.utc),
                url_used=search_url,
                confidence=0.1,
            )

        posts = []
        sentiment_signals = {"positive": 0, "negative": 0, "neutral": 0}

        for child in posts_data[:10]:
            post = child.get("data", {})
            title = post.get("title", "")
            score = post.get("score", 0)
            subreddit = post.get("subreddit", "")
            url = f"https://reddit.com{post.get('permalink', '')}"
            selftext = post.get("selftext", "")[:300]

            # Простой анализ тональности по ключевым словам
            combined = (title + " " + selftext).lower()
            if any(w in combined for w in ["great", "love", "best", "amazing", "recommend", "excellent"]):
                sentiment_signals["positive"] += 1
            elif any(w in combined for w in ["bad", "scam", "worst", "terrible", "avoid", "fraud", "complaint"]):
                sentiment_signals["negative"] += 1
            else:
                sentiment_signals["neutral"] += 1

            posts.append({
                "title": title,
                "subreddit": subreddit,
                "score": score,
                "url": url,
                "snippet": selftext[:200],
                "num_comments": post.get("num_comments", 0),
            })

        return CollectorResult(
            source_name=self.source_name,
            status="success",
            data={
                "query": query,
                "total_found": len(posts_data),
                "posts": posts,
                "sentiment_signals": sentiment_signals,
                "top_subreddits": list({p["subreddit"] for p in posts if p["subreddit"]}),
            },
            retrieved_at=datetime.now(timezone.utc),
            url_used=search_url,
            confidence=0.65,
        )
