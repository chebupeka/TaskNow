from pydantic import BaseModel

from app.schemas.messages import MessageRead
from app.schemas.orders import OrderRead
from app.schemas.payments import PaymentRead


class AdminDisputeDetail(BaseModel):
    order: OrderRead
    payment: PaymentRead | None
    messages: list[MessageRead]


class AdminDisputeResolveRequest(BaseModel):
    resolution: str
    note: str | None = None
