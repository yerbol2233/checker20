from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from logging_config import setup_logging

from api.sessions import router as sessions_router
from api.stream import router as stream_router
from api.dashboard import router as dashboard_router
from api.feedback import router as feedback_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    setup_logging()
    yield


app = FastAPI(
    title="CIA — Company Intelligence Agent",
    description="B2B компания-разведчик: паспорт + outreach за минуты",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://frontend:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_router, prefix="/api")
app.include_router(stream_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(feedback_router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker/monitoring."""
    from database import engine
    from config import settings

    health = {"status": "ok", "service": "cia-backend"}
    # Quick DB check
    try:
        async with engine.connect() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
        health["database"] = "ok"
    except Exception as exc:
        health["database"] = f"error: {exc}"
        health["status"] = "degraded"

    # Quick Redis check
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        health["redis"] = "ok"
    except Exception as exc:
        health["redis"] = f"error: {exc}"
        health["status"] = "degraded"

    return health
