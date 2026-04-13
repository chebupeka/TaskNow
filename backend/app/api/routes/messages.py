from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.message import ChatMessage
from app.models.order import Order, OrderStatus
from app.models.user import User, UserRole, utc_now
from app.schemas.messages import MessageCreate, MessageRead

router = APIRouter(tags=["messages"])

CHAT_ORDER_STATUSES = {
    OrderStatus.ACCEPTED,
    OrderStatus.IN_PROGRESS,
    OrderStatus.COMPLETION_REQUESTED,
    OrderStatus.DISPUTED,
}


async def require_chat_access(db: AsyncSession, order_id: UUID, user: User) -> Order:
    order = await db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")
    is_order_participant = order.customer_id == user.id or order.worker_id == user.id
    is_dispute_admin = user.role == UserRole.ADMIN and order.status == OrderStatus.DISPUTED
    if not is_order_participant and not is_dispute_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к чату")
    if order.status not in CHAT_ORDER_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Чат доступен после принятия заказа и до завершения")
    return order


@router.get("/messages/unread-count", response_model=int)
async def get_unread_messages_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(ChatMessage)
        .join(Order, Order.id == ChatMessage.order_id)
        .where(Order.status.in_(CHAT_ORDER_STATUSES))
        .where(or_(Order.customer_id == current_user.id, Order.worker_id == current_user.id))
        .where(ChatMessage.sender_id != current_user.id)
        .where(ChatMessage.read_at.is_(None))
    )
    return int(count or 0)


@router.get("/orders/{order_id}/messages", response_model=list[MessageRead])
async def list_messages(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessage]:
    await require_chat_access(db, order_id, current_user)
    messages = list(
        (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.order_id == order_id)
                .order_by(ChatMessage.sent_at.asc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )

    changed = False
    for message in messages:
        if message.sender_id != current_user.id and message.read_at is None:
            message.read_at = utc_now()
            changed = True
    if changed:
        await db.commit()
        for message in messages:
            await db.refresh(message)

    return messages


@router.post("/orders/{order_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def send_message(
    order_id: UUID,
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatMessage:
    await require_chat_access(db, order_id, current_user)
    message = ChatMessage(
        order_id=order_id,
        sender_id=current_user.id,
        body=payload.body.strip(),
        client_message_id=payload.client_message_id,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message
