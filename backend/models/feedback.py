import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy import String, Text, Boolean, Integer
from database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=utcnow
    )

    result: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # replied | read_no_reply | not_read
    passport_useful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    best_hook: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_hook_custom: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_strategy: Mapped[str | None] = mapped_column(String(30), nullable=True)
    message_strategy_custom: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
