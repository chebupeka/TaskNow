from pydantic import BaseModel, Field, field_validator

from app.models.user import UserRole
from app.schemas.users import UserRead, WorkerRead, normalize_phone


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole
    phone: str | None = Field(default=None, max_length=32)
    skills: list[str] = Field(default_factory=list, max_length=20)
    current_lat: float | None = None
    current_lng: float | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead | WorkerRead


class ProfileUpdateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=255)
    phone: str | None = Field(default=None, max_length=32)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AvatarUpdateRequest(BaseModel):
    avatar_url: str | None = Field(default=None, max_length=1_400_000)


class IdentityVerificationRequest(BaseModel):
    passport_full_name: str = Field(min_length=2, max_length=160)
    passport_number: str = Field(min_length=6, max_length=32)
