from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID as PyUUID, uuid4

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import utc_now


class OrderStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETION_REQUESTED = "completion_requested"
    COMPLETED = "completed"
    REVIEWED = "reviewed"
    DISPUTED = "disputed"
    CANCELED = "canceled"


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_status_scheduled_at", "status", "scheduled_at"),)

    id: Mapped[PyUUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    customer_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    worker_id: Mapped[PyUUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    budget_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    city: Mapped[str | None] = mapped_column(String(120), index=True)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(
            OrderStatus,
            name="order_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=OrderStatus.PENDING,
        index=True,
        nullable=False,
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    customer: Mapped[User] = relationship(
        "User",
        back_populates="customer_orders",
        foreign_keys=[customer_id],
    )
    worker: Mapped[User | None] = relationship(
        "User",
        back_populates="assigned_orders",
        foreign_keys=[worker_id],
    )
    review: Mapped[Review | None] = relationship(
        "Review",
        back_populates="order",
        cascade="all, delete-orphan",
        uselist=False,
    )
    notifications: Mapped[list[Notification]] = relationship("Notification", back_populates="order")
