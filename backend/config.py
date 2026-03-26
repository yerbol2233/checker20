from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    # Railway передаёт DATABASE_URL в формате postgresql://...
    # Мы автоматически конвертируем в postgresql+asyncpg://...
    database_url: str = "postgresql+asyncpg://cia_user:cia_password@localhost:5432/cia_db"

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            # Heroku/Railway иногда используют postgres:// (устаревший алиас)
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # LLM
    anthropic_api_key: str = ""
    google_api_key: str = ""
    openai_api_key: str = ""

    # ScrapeOps
    scrapeops_api_key: str = ""
    scrapeops_url: str = "https://proxy.scrapeops.io/v1/"
    # ScrapeOps HTTP proxy mode (для DDGS и других библиотек поддерживающих стандартный прокси)
    # Формат: http://API_KEY:@proxy.scrapeops.io:5353
    @property
    def scrapeops_http_proxy(self) -> str:
        if self.scrapeops_api_key:
            return f"http://{self.scrapeops_api_key}:@proxy.scrapeops.io:5353"
        return ""

    # Apollo
    apollo_api_key: str = ""

    # Serper.dev (Google Search API)
    serper_api_key: str = ""

    # CORS — через запятую: https://your-app.vercel.app,http://localhost:3000
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://frontend:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # App
    debug: bool = False
    log_level: str = "INFO"
    secret_key: str = "change_me_in_production"

    # Cache
    company_cache_ttl_days: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
