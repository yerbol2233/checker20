import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy import Float, Text
from database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Passport(Base):
    __tablename__ = "passports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=utcnow
    )

    # Block 1: General profile
    block1_general: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    block1_sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    block1_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Block 2: Sales model
    block2_sales_model: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    block2_sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    block2_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Block 3: Pains
    block3_pains: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    block3_sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    block3_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Block 4: Key people
    block4_people: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    block4_sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    block4_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Block 5: Context / hooks
    block5_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    block5_sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    block5_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Block 6: Competitors
    block6_competitors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    block6_sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    block6_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Block 7: Readiness to buy
    block7_readiness: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    block7_sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    block7_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Block 8: Reputation / reviews
    block8_reputation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    block8_sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    block8_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Block 9: Entry triggers
    block9_triggers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    block9_sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    block9_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Block 10: LPR profile
    block10_lpr: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    block10_sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    block10_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Block 11: Industry context
    block11_industry: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    block11_sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    block11_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Meta
    top3_hooks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    raw_collected_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
