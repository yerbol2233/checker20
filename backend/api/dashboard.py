"""
GET /sessions/{id}/dashboard — полные данные дашборда (паспорт + outreach + агент-таймлайн).
"""
import uuid

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.session import Session
from models.passport import Passport
from models.outreach import OutreachText
from models.token_log import AgentLog, TokenLog

router = APIRouter(prefix="/sessions", tags=["dashboard"])


@router.get("/{session_id}/dashboard")
async def get_dashboard(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Возвращает все данные для дашборда:
    - статус сессии
    - паспорт (11 блоков)
    - outreach тексты
    - таймлайн агентов
    - суммарные расходы токенов
    """
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id format")

    # Session
    session_result = await db.execute(select(Session).where(Session.id == sid))
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Passport
    passport_result = await db.execute(
        select(Passport).where(Passport.session_id == sid)
    )
    passport = passport_result.scalar_one_or_none()

    # Outreach
    outreach_result = await db.execute(
        select(OutreachText).where(OutreachText.session_id == sid)
    )
    outreach = outreach_result.scalar_one_or_none()

    # Agent logs (таймлайн)
    logs_result = await db.execute(
        select(AgentLog)
        .where(AgentLog.session_id == sid)
        .order_by(AgentLog.created_at)
    )
    logs = logs_result.scalars().all()

    # Token costs
    tokens_result = await db.execute(
        select(TokenLog).where(TokenLog.session_id == sid)
    )
    token_logs = tokens_result.scalars().all()

    total_cost = sum(t.cost_usd for t in token_logs)
    total_tokens = sum(t.total_tokens for t in token_logs)

    return {
        "session": _serialize_session(session),
        "passport": _serialize_passport(passport),
        "outreach": _serialize_outreach(outreach),
        "agent_timeline": [_serialize_log(l) for l in logs],
        "token_summary": {
            "total_cost_usd": round(total_cost, 6),
            "total_tokens": total_tokens,
            "by_provider": _group_tokens_by_provider(token_logs),
        },
    }


# ── Serializers ────────────────────────────────────────────────────────────

def _serialize_session(s: Session) -> dict:
    return {
        "id": str(s.id),
        "status": s.status,
        "website_url": s.website_url,
        "linkedin_lpr_url": s.linkedin_lpr_url,
        "company_name": s.company_name,
        "resolved_company_name": s.resolved_company_name,
        "resolved_domain": s.resolved_domain,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "pipeline_started_at": s.pipeline_started_at.isoformat() if s.pipeline_started_at else None,
        "pipeline_finished_at": s.pipeline_finished_at.isoformat() if s.pipeline_finished_at else None,
        "duration_seconds": s.duration_seconds,
        "is_cached": s.is_cached,
        "completeness_score": s.completeness_score,
        "completeness_status": s.completeness_status,
        "incompleteness_reasons": s.incompleteness_reasons or [],
        "errors": s.errors or [],
    }


def _serialize_passport(p: Passport | None) -> dict | None:
    if not p:
        return None
    return {
        "id": str(p.id),
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "blocks": {
            "1_general": {"data": p.block1_general, "sources": p.block1_sources, "confidence": p.block1_confidence},
            "2_sales_model": {"data": p.block2_sales_model, "sources": p.block2_sources, "confidence": p.block2_confidence},
            "3_pains": {"data": p.block3_pains, "sources": p.block3_sources, "confidence": p.block3_confidence},
            "4_people": {"data": p.block4_people, "sources": p.block4_sources, "confidence": p.block4_confidence},
            "5_context": {"data": p.block5_context, "sources": p.block5_sources, "confidence": p.block5_confidence},
            "6_competitors": {"data": p.block6_competitors, "sources": p.block6_sources, "confidence": p.block6_confidence},
            "7_readiness": {"data": p.block7_readiness, "sources": p.block7_sources, "confidence": p.block7_confidence},
            "8_reputation": {"data": p.block8_reputation, "sources": p.block8_sources, "confidence": p.block8_confidence},
            "9_triggers": {"data": p.block9_triggers, "sources": p.block9_sources, "confidence": p.block9_confidence},
            "10_lpr": {"data": p.block10_lpr, "sources": p.block10_sources, "confidence": p.block10_confidence},
            "11_industry": {"data": p.block11_industry, "sources": p.block11_sources, "confidence": p.block11_confidence},
        },
        "top3_hooks": p.top3_hooks,
    }


def _serialize_outreach(o: OutreachText | None) -> dict | None:
    if not o:
        return None
    return {
        "id": str(o.id),
        "lpr_type": o.lpr_type,
        "lpr_type_rationale": o.lpr_type_rationale,
        "selected_path": o.selected_path,
        "path_selection_rationale": o.path_selection_rationale,
        "warmup_comments": o.warmup_comments or [],
        "linkedin_messages": o.linkedin_messages or [],
        "followup_message": o.followup_message,
        "followup_new_angle": o.followup_new_angle,
        "email_subject": o.email_subject,
        "email_body": o.email_body,
        "copywriting_rules_applied": o.copywriting_rules_applied or [],
    }


def _serialize_log(l: AgentLog) -> dict:
    return {
        "id": l.id,
        "agent_name": l.agent_name,
        "event_type": l.event_type,
        "message": l.message,
        "details": l.details,
        "duration_ms": l.duration_ms,
        "is_error": l.is_error,
        "created_at": l.created_at.isoformat() if l.created_at else None,
    }


def _group_tokens_by_provider(token_logs: list[TokenLog]) -> dict:
    result: dict[str, dict] = {}
    for t in token_logs:
        if t.llm_provider not in result:
            result[t.llm_provider] = {"tokens": 0, "cost_usd": 0.0, "calls": 0}
        result[t.llm_provider]["tokens"] += t.total_tokens
        result[t.llm_provider]["cost_usd"] += t.cost_usd
        result[t.llm_provider]["calls"] += 1
    # Round costs
    for v in result.values():
        v["cost_usd"] = round(v["cost_usd"], 6)
    return result
