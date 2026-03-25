from collectors.base import (
    BaseCollector,
    CollectorResult,
    make_failed_result,
    make_not_applicable_result,
)
from collectors.website_collector import WebsiteCollector
from collectors.duckduckgo_collector import DuckDuckGoCollector
from collectors.linkedin_company import LinkedInCompanyCollector
from collectors.linkedin_person import LinkedInPersonCollector
from collectors.glassdoor_collector import GlassdoorCollector
from collectors.crunchbase_collector import CrunchbaseCollector
from collectors.twitter_collector import TwitterCollector
from collectors.g2_collector import G2Collector
from collectors.capterra_collector import CapterraCollector
from collectors.trustpilot_collector import TrustpilotCollector
from collectors.yelp_collector import YelpCollector
from collectors.google_reviews_collector import GoogleReviewsCollector
from collectors.indeed_collector import IndeedCollector
from collectors.similarweb_collector import SimilarWebCollector
from collectors.builtwith_collector import BuiltWithCollector
from collectors.sec_edgar_collector import SECEdgarCollector
from collectors.youtube_collector import YouTubeCollector
from collectors.apollo_collector import ApolloCollector
from collectors.reddit_collector import RedditCollector


# Все коллекторы для параллельного запуска в пайплайне
ALL_COLLECTORS: list[type[BaseCollector]] = [
    WebsiteCollector,
    DuckDuckGoCollector,
    LinkedInCompanyCollector,
    LinkedInPersonCollector,
    GlassdoorCollector,
    CrunchbaseCollector,
    TwitterCollector,
    G2Collector,
    CapterraCollector,
    TrustpilotCollector,
    YelpCollector,
    GoogleReviewsCollector,
    IndeedCollector,
    SimilarWebCollector,
    BuiltWithCollector,
    SECEdgarCollector,
    YouTubeCollector,
    ApolloCollector,
    RedditCollector,
]


__all__ = [
    "BaseCollector",
    "CollectorResult",
    "make_failed_result",
    "make_not_applicable_result",
    "ALL_COLLECTORS",
    "WebsiteCollector",
    "DuckDuckGoCollector",
    "LinkedInCompanyCollector",
    "LinkedInPersonCollector",
    "GlassdoorCollector",
    "CrunchbaseCollector",
    "TwitterCollector",
    "G2Collector",
    "CapterraCollector",
    "TrustpilotCollector",
    "YelpCollector",
    "GoogleReviewsCollector",
    "IndeedCollector",
    "SimilarWebCollector",
    "BuiltWithCollector",
    "SECEdgarCollector",
    "YouTubeCollector",
    "ApolloCollector",
    "RedditCollector",
]
