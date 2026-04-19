import uuid
from datetime import datetime

from sqlalchemy import String, Integer, BigInteger, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tracked_people.id"))
    type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    flow: Mapped[str] = mapped_column(String(30), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    urgency: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    reasoning: Mapped[str | None] = mapped_column(Text)
    suggested_action: Mapped[str | None] = mapped_column(Text)
    target_company: Mapped[str | None] = mapped_column(String(255))
    target_company_size: Mapped[int | None] = mapped_column(Integer)
    target_company_revenue_lower: Mapped[int | None] = mapped_column(BigInteger)
    target_company_revenue_upper: Mapped[int | None] = mapped_column(BigInteger)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="signals")
    person = relationship("TrackedPerson")
    outreach_drafts = relationship("OutreachDraft", back_populates="signal", cascade="all, delete-orphan")
