from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.payment import PaymentStatus, PayoutStatus


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    order_title: str | None = None
    customer_id: UUID
    worker_id: UUID | None
    amount: int
    service_fee: int
    worker_amount: int
    status: PaymentStatus
    created_at: datetime
    updated_at: datetime


class WalletRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    balance_available: int
    balance_paid_out: int


class PayoutRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    worker_id: UUID
    amount: int
    status: PayoutStatus
    created_at: datetime


class PaymentsDashboard(BaseModel):
    wallet: WalletRead
    payments: list[PaymentRead]
    payouts: list[PayoutRead]
    hold_total: int
