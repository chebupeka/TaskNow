from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID as PyUUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import utc_now


class NotificationKind(str, Enum):
    ORDER_PENDING = "order_pending"
    ORDER_ASSIGNED = "order_assigned"
    ORDER_REASSIGNED = "order_reassigned"
    ORDER_ACCEPTED = "order_accepted"
    ORDER_DECLINED = "order_declined"
    ORDER_COMPLETION_REQUESTED = "order_completion_requested"
    ORDER_COMPLETED = "order_completed"
    ORDER_READY_TO_REVIEW = "order_ready_to_review"
    REVIEW_RECEIVED = "review_received"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[PyUUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[PyUUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[PyUUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    kind: Mapped[NotificationKind] = mapped_column(
        SAEnum(
            NotificationKind,
            name="notification_kind",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped[User] = relationship("User", back_populates="notifications")
    order: Mapped[Order | None] = relationship("Order", back_populates="notifications")
