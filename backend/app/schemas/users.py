from datetime import datetime
import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import UserRole, WorkerAvailability


PHONE_PATTERN = re.compile(r"^(?:\+7|8)\d{10}$")


def normalize_phone(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None

    normalized = re.sub(r"[\s().-]", "", value.strip())
    if not PHONE_PATTERN.fullmatch(normalized):
        raise ValueError("Телефон должен быть в формате +7XXXXXXXXXX или 8XXXXXXXXXX")

    return "+7" + normalized[-10:]


class CustomerCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value)


class WorkerCreate(CustomerCreate):
    skills: list[str] = Field(default_factory=list, max_length=20)
    city: str | None = Field(default=None, max_length=120)
    current_lat: float | None = None
    current_lng: float | None = None

    @field_validator("city")
    @classmethod
    def validate_city(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: UserRole
    full_name: str
    phone: str | None
    email: str | None
    avatar_url: str | None
    identity_status: str
    is_active: bool
    created_at: datetime


class WorkerRead(BaseModel):
    id: UUID
    role: UserRole = UserRole.WORKER
    full_name: str
    phone: str | None
    email: str | None
    avatar_url: str | None
    identity_status: str
    skills: list[str]
    availability: WorkerAvailability
    rating_avg: float
    rating_count: int
    completed_orders: int
    city: str | None
    current_lat: float | None
    current_lng: float | None
