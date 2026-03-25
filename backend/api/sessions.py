"""
POST /sessions   — создать новую сессию анализа
GET  /sessions/{id} — получить статус/данные сессии
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, HttpUrl, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.session import Session
from tasks.pipeline_task import run_pipeline

router = APIRouter(prefix="/sessions", tags=["sessions"])


# ── Schemas ────────────────────────────────────────────────────────────────

class SessionCreateRequest(BaseModel):
    website_url: str
    linkedin_lpr_url: str | None = None
    company_name: str | None = None

    @field_validator("website_url")
    @classmethod
    def normalize_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            v = "https://" + v
        return v


class SessionResponse(BaseModel):
    id: str
    status: str
    website_url: str
    linkedin_lpr_url: str | None
    company_name: str | None
    resolved_company_name: str | None
    resolved_domain: str | None
    created_at: str
    updated_at: str
    pipeline_started_at: str | None
    pipeline_finished_at: str | None
    duration_seconds: float | None
    is_cached: bool
    completeness_score: int | None
    completeness_status: str | None
    errors: list

    @classmethod
    def from_orm(cls, s: Session) -> "SessionResponse":
        def fmt(dt: datetime | None) -> str | None:
            return dt.isoformat() if dt else None

        return cls(
            id=str(s.id),
            status=s.status,
            website_url=s.website_url,
            linkedin_lpr_url=s.linkedin_lpr_url,
            company_name=s.company_name,
            resolved_company_name=s.resolved_company_name,
            resolved_domain=s.resolved_domain,
            created_at=fmt(s.created_at),
            updated_at=fmt(s.updated_at),
            pipeline_started_at=fmt(s.pipeline_started_at),
            pipeline_finished_at=fmt(s.pipeline_finished_at),
            duration_seconds=s.duration_seconds,
            is_cached=s.is_cached,
            completeness_score=s.completeness_score,
            completeness_status=s.completeness_status,
            errors=s.errors or [],
        )


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    body: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """Создать сессию и запустить пайплайн анализа."""
    session = Session(
        id=uuid.uuid4(),
        status="pending",
        website_url=body.website_url,
        linkedin_lpr_url=body.linkedin_lpr_url,
        company_name=body.company_name,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        errors=[],
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    # Запускаем Celery задачу
    run_pipeline.delay(str(session.id))

    return SessionResponse.from_orm(session)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """Получить текущий статус сессии."""
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id format")

    result = await db.execute(select(Session).where(Session.id == sid))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse.from_orm(session)
