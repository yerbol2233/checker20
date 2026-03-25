"""
POST /sessions/{id}/feedback — сохранить обратную связь по результату.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.session import Session
from models.feedback import Feedback

router = APIRouter(prefix="/sessions", tags=["feedback"])


class FeedbackRequest(BaseModel):
    result: str | None = None          # replied | read_no_reply | not_read
    passport_useful: bool | None = None
    best_hook: int | None = None       # 0, 1, 2 или None = 'other'
    best_hook_custom: str | None = None
    message_strategy: str | None = None  # value | own | curiosity | custom
    message_strategy_custom: str | None = None
    notes: str | None = None


class FeedbackResponse(BaseModel):
    id: str
    session_id: str
    created_at: str


@router.post("/{session_id}/feedback", response_model=FeedbackResponse, status_code=201)
async def create_feedback(
    session_id: str,
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """Сохранить обратную связь по сессии."""
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id format")

    session_result = await db.execute(select(Session).where(Session.id == sid))
    if not session_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")

    feedback = Feedback(
        id=uuid.uuid4(),
        session_id=sid,
        created_at=datetime.now(timezone.utc),
        result=body.result,
        passport_useful=body.passport_useful,
        best_hook=body.best_hook,
        best_hook_custom=body.best_hook_custom,
        message_strategy=body.message_strategy,
        message_strategy_custom=body.message_strategy_custom,
        notes=body.notes,
    )
    db.add(feedback)
    await db.flush()
    await db.refresh(feedback)

    return FeedbackResponse(
        id=str(feedback.id),
        session_id=str(feedback.session_id),
        created_at=feedback.created_at.isoformat(),
    )
