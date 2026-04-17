from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID as PyUUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    CUSTOMER = "customer"
    WORKER = "worker"
    ADMIN = "admin"


class WorkerAvailability(str, Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


class User(Base):
    __tablename__ = "users"

    id: Mapped[PyUUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", values_callable=lambda enum: [item.value for item in enum]),
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    identity_status: Mapped[str] = mapped_column(String(32), default="not_verified", nullable=False)
    passport_full_name: Mapped[str | None] = mapped_column(String(160))
    passport_number: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    worker_profile: Mapped[WorkerProfile | None] = relationship(
        "WorkerProfile",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    customer_orders: Mapped[list[Order]] = relationship(
        "Order",
        back_populates="customer",
        foreign_keys="Order.customer_id",
    )
    assigned_orders: Mapped[list[Order]] = relationship(
        "Order",
        back_populates="worker",
        foreign_keys="Order.worker_id",
    )
    notifications: Mapped[list[Notification]] = relationship("Notification", back_populates="user")


class WorkerProfile(Base):
    __tablename__ = "worker_profiles"

    user_id: Mapped[PyUUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    skills: Mapped[list[str]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), default=list, nullable=False)
    availability: Mapped[WorkerAvailability] = mapped_column(
        SAEnum(
            WorkerAvailability,
            name="worker_availability",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=WorkerAvailability.OFFLINE,
        index=True,
        nullable=False,
    )
    rating_avg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rating_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_orders: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_lat: Mapped[float | None] = mapped_column(Float)
    current_lng: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    user: Mapped[User] = relationship("User", back_populates="worker_profile")
