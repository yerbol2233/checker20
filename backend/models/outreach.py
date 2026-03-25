import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy import String, Text
from database import Base


def utcnow():
    return datetime.now(timezone.utc)


class OutreachText(Base):
    __tablename__ = "outreach_texts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=utcnow
    )

    lpr_type: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # creator | quiet_pro | networker | newcomer
    selected_path: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # value | own | curiosity

    # 2-3 warmup comments
    warmup_comments: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # 3 LinkedIn message variants
    linkedin_messages: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Follow-up
    followup_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    followup_new_angle: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Email
    email_subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Rationale
    lpr_type_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    path_selection_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    copywriting_rules_applied: Mapped[list | None] = mapped_column(JSONB, nullable=True)
