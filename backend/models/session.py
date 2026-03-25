import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=utcnow, onupdate=utcnow
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending | running | completed | failed | cached

    # Input
    website_url: Mapped[str] = mapped_column(Text, nullable=False)
    linkedin_lpr_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Resolved
    resolved_company_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_domain: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pipeline metadata
    pipeline_started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    pipeline_finished_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_cached: Mapped[bool] = mapped_column(Boolean, default=False)
    cache_source_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Completeness
    completeness_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completeness_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    incompleteness_reasons: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Errors
    errors: Mapped[list] = mapped_column(JSONB, default=list)
