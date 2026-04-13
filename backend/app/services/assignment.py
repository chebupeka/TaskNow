from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationKind
from app.models.order import Order, OrderStatus
from app.models.user import User, UserRole, WorkerAvailability, WorkerProfile, utc_now

BUSY_ORDER_STATUSES = (
    OrderStatus.ASSIGNED,
    OrderStatus.ACCEPTED,
    OrderStatus.IN_PROGRESS,
    OrderStatus.COMPLETION_REQUESTED,
)


async def assign_best_worker(
    session: AsyncSession,
    order: Order,
    exclude_worker_ids: set[UUID] | None = None,
) -> User | None:
    busy_worker = (
        select(Order.id)
        .where(Order.worker_id == WorkerProfile.user_id)
        .where(Order.status.in_(BUSY_ORDER_STATUSES))
        .exists()
    )

    statement = (
        select(WorkerProfile, User)
        .join(User, WorkerProfile.user_id == User.id)
        .where(User.role == UserRole.WORKER)
        .where(User.is_active.is_(True))
        .where(WorkerProfile.availability == WorkerAvailability.AVAILABLE)
        .where(~busy_worker)
        .order_by(WorkerProfile.rating_avg.desc(), WorkerProfile.completed_orders.desc(), User.created_at.asc())
        .limit(1)
    )

    if exclude_worker_ids:
        statement = statement.where(WorkerProfile.user_id.notin_(exclude_worker_ids))

    row = (await session.execute(statement)).first()
    if row is None:
        order.worker_id = None
        order.status = OrderStatus.PENDING
        order.assigned_at = None
        return None

    profile, worker = row
    profile.availability = WorkerAvailability.BUSY
    order.worker_id = worker.id
    order.status = OrderStatus.ASSIGNED
    order.assigned_at = utc_now()
    return worker


async def assign_next_pending_order_to_worker(session: AsyncSession, worker: User) -> Order | None:
    profile = await session.get(WorkerProfile, worker.id)
    if worker.role != UserRole.WORKER or profile is None or profile.availability != WorkerAvailability.AVAILABLE:
        return None

    busy_order = (
        await session.execute(
            select(Order.id)
            .where(Order.worker_id == worker.id)
            .where(Order.status.in_(BUSY_ORDER_STATUSES))
            .limit(1)
        )
    ).scalar_one_or_none()
    if busy_order is not None:
        return None

    order = (
        await session.execute(
            select(Order)
            .where(Order.status == OrderStatus.PENDING)
            .where(Order.worker_id.is_(None))
            .order_by(Order.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if order is None:
        return None

    profile.availability = WorkerAvailability.BUSY
    order.worker_id = worker.id
    order.status = OrderStatus.ASSIGNED
    order.assigned_at = utc_now()
    session.add_all(
        [
            Notification(
                user_id=worker.id,
                order_id=order.id,
                kind=NotificationKind.ORDER_ASSIGNED,
                title="Новый заказ",
                body=f"{order.address}: {order.description[:120]}",
            ),
            Notification(
                user_id=order.customer_id,
                order_id=order.id,
                kind=NotificationKind.ORDER_ASSIGNED,
                title="Исполнитель назначен",
                body=f"Заказ передан работнику {worker.full_name}.",
            ),
        ]
    )
    return order
