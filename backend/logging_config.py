"""
Централизованная настройка логирования CIA.

Файловые логи с ежедневной ротацией (30 дней хранения):
- logs/app.log       — основной лог
- logs/scraping.log  — скрапинг / HTTP запросы
- logs/llm.log       — LLM вызовы
- logs/token_costs.csv — CSV расходов (управляется TokenTracker)
"""
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from config import settings

LOGS_DIR = Path(__file__).parent / "logs"

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
LOG_DATEFMT = "%Y-%m-%dT%H:%M:%SZ"

_CONFIGURED = False


def setup_logging() -> None:
    """Настроить логирование один раз при старте приложения."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    LOGS_DIR.mkdir(exist_ok=True)

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # ── Корневой логгер ──────────────────────────────────────────────────
    root = logging.getLogger()
    root.setLevel(level)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))
    root.addHandler(console)

    # ── Файловые логгеры ─────────────────────────────────────────────────
    file_loggers = {
        "cia.app": "app.log",
        "cia.scraping": "scraping.log",
        "cia.llm": "llm.log",
    }

    for logger_name, filename in file_loggers.items():
        _setup_file_logger(logger_name, LOGS_DIR / filename, level)

    # Тихие библиотеки
    for noisy in ("httpx", "httpcore", "celery", "kombu", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("cia.app").info("Logging configured (level=%s)", settings.log_level)


def _setup_file_logger(name: str, filepath: Path, level: int) -> None:
    """Настроить логгер с ежедневной ротацией (хранение 30 дней)."""
    log = logging.getLogger(name)
    log.setLevel(level)
    log.propagate = False  # не дублировать в корневой логгер

    if log.handlers:
        return  # уже настроен

    handler = TimedRotatingFileHandler(
        filename=str(filepath),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        utc=True,
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))
    handler.setLevel(level)
    log.addHandler(handler)
