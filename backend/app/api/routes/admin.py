from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.message import ChatMessage
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole, WorkerAvailability, WorkerProfile, utc_now
from app.schemas.admin import AdminDisputeDetail, AdminDisputeResolveRequest
from app.schemas.messages import MessageRead
from app.schemas.orders import OrderRead
from app.schemas.payments import PaymentRead
from app.services.payments import release_payment_to_worker

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Требуется роль администратора")


async def get_disputed_order_or_404(db: AsyncSession, order_id: UUID) -> Order:
    order = await db.get(Order, order_id)
    if order is None or order.status != OrderStatus.DISPUTED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Спор не найден")
    return order


async def get_order_payment(db: AsyncSession, order_id: UUID) -> Payment | None:
    return (
        await db.execute(select(Payment).where(Payment.order_id == order_id))
    ).scalar_one_or_none()


async def get_order_messages(db: AsyncSession, order_id: UUID) -> list[ChatMessage]:
    return list(
        (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.order_id == order_id)
                .order_by(ChatMessage.sent_at.asc())
                .limit(300)
            )
        )
        .scalars()
        .all()
    )


async def enrich_order_people(db: AsyncSession, order: Order) -> Order:
    users = {
        user.id: user
        for user in (
            await db.execute(select(User).where(User.id.in_([order.customer_id, order.worker_id])))
        )
        .scalars()
        .all()
        if user is not None
    }
    customer = users.get(order.customer_id)
    worker = users.get(order.worker_id) if order.worker_id is not None else None
    profile = await db.get(WorkerProfile, order.worker_id) if order.worker_id is not None else None
    order.customer_full_name = customer.full_name if customer else None
    order.customer_avatar_url = customer.avatar_url if customer else None
    order.worker_full_name = worker.full_name if worker else None
    order.worker_avatar_url = worker.avatar_url if worker else None
    order.worker_rating_avg = profile.rating_avg if profile else None
    order.worker_rating_count = profile.rating_count if profile else None
    return order


async def build_dispute_detail(db: AsyncSession, order: Order) -> AdminDisputeDetail:
    order = await enrich_order_people(db, order)
    payment = await get_order_payment(db, order.id)
    messages = await get_order_messages(db, order.id)
    return AdminDisputeDetail(
        order=OrderRead.model_validate(order),
        payment=PaymentRead.model_validate(payment) if payment else None,
        messages=[MessageRead.model_validate(message) for message in messages],
    )


def add_admin_message(db: AsyncSession, order_id: UUID, admin: User, body: str) -> None:
    db.add(
        ChatMessage(
            order_id=order_id,
            sender_id=admin.id,
            body=body,
            client_message_id=None,
        )
    )


@router.get("/disputes", response_model=list[OrderRead])
async def list_disputes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Order]:
    require_admin(current_user)
    orders = list(
        (
            await db.execute(
                select(Order)
                .where(Order.status == OrderStatus.DISPUTED)
                .order_by(Order.updated_at.desc(), Order.created_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    for order in orders:
        await enrich_order_people(db, order)
    return orders


@router.get("/disputes/{order_id}", response_model=AdminDisputeDetail)
async def get_dispute(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdminDisputeDetail:
    require_admin(current_user)
    order = await get_disputed_order_or_404(db, order_id)
    return await build_dispute_detail(db, order)


@router.post("/disputes/{order_id}/resolve", response_model=AdminDisputeDetail)
async def resolve_dispute(
    order_id: UUID,
    payload: AdminDisputeResolveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdminDisputeDetail:
    require_admin(current_user)
    order = await get_disputed_order_or_404(db, order_id)
    payment = await get_order_payment(db, order.id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Платеж по спору не найден")

    resolution = payload.resolution.strip().lower()
    note = payload.note.strip() if payload.note else ""
    if resolution == "release_to_worker":
        order.status = OrderStatus.COMPLETED
        order.completed_at = utc_now()
        await release_payment_to_worker(db, order)
        add_admin_message(
            db,
            order.id,
            current_user,
            note or "Спор решен в пользу исполнителя. Средства выплачены исполнителю.",
        )
    elif resolution == "refund_customer":
        order.status = OrderStatus.CANCELED
        order.completed_at = utc_now()
        payment.status = PaymentStatus.REFUNDED
        add_admin_message(
            db,
            order.id,
            current_user,
            note or "Спор решен в пользу заказчика. Средства возвращены заказчику.",
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Доступные решения: release_to_worker или refund_customer",
        )

    if order.worker_id is not None:
        profile = await db.get(WorkerProfile, order.worker_id)
        if profile is not None:
            profile.availability = WorkerAvailability.AVAILABLE

    await db.commit()
    await db.refresh(order)
    return await build_dispute_detail(db, order)
