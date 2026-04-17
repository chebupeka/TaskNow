from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.order import OrderStatus


def normalize_city(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    return normalized or None


class OrderCreate(BaseModel):
    customer_id: UUID
    description: str = Field(min_length=5, max_length=2000)
    budget_amount: int = Field(ge=1, le=10_000_000)
    city: str = Field(min_length=2, max_length=120)
    address: str = Field(min_length=3, max_length=500)
    scheduled_at: datetime

    @field_validator("city")
    @classmethod
    def validate_city(cls, value: str) -> str:
        normalized = normalize_city(value)
        if normalized is None:
            raise ValueError("Укажите город")
        return normalized


class OrderCreateForCurrentUser(BaseModel):
    description: str = Field(min_length=5, max_length=2000)
    budget_amount: int = Field(ge=1, le=10_000_000)
    city: str = Field(min_length=2, max_length=120)
    address: str = Field(min_length=3, max_length=500)
    scheduled_at: datetime

    @field_validator("city")
    @classmethod
    def validate_city(cls, value: str) -> str:
        normalized = normalize_city(value)
        if normalized is None:
            raise ValueError("Укажите город")
        return normalized


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    customer_full_name: str | None = None
    customer_avatar_url: str | None = None
    worker_id: UUID | None
    worker_full_name: str | None = None
    worker_avatar_url: str | None = None
    worker_rating_avg: float | None = None
    worker_rating_count: int | None = None
    description: str
    budget_amount: int
    city: str | None
    address: str
    scheduled_at: datetime
    status: OrderStatus
    assigned_at: datetime | None
    decision_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkerOrderAction(BaseModel):
    worker_id: UUID


class ReviewCreate(BaseModel):
    customer_id: UUID
    score: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewCreateForCurrentUser(BaseModel):
    score: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    customer_id: UUID
    worker_id: UUID
    score: int
    comment: str | None
    created_at: datetime
    order_title: str | None = None
    customer_full_name: str | None = None
