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


def normalize_city(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().lower().split())
    return normalized or None


async def assign_best_worker(
    session: AsyncSession,
    order: Order,
    exclude_worker_ids: set[UUID] | None = None,
) -> User | None:
    order_city = normalize_city(order.city)
    if order_city is None:
        order.worker_id = None
        order.status = OrderStatus.PENDING
        order.assigned_at = None
        return None

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
        .where(WorkerProfile.city.is_not(None))
        .where(~busy_worker)
    )

    if exclude_worker_ids:
        statement = statement.where(WorkerProfile.user_id.notin_(exclude_worker_ids))

    rows = (await session.execute(statement)).all()
    candidates = [
        (profile, worker)
        for profile, worker in rows
        if normalize_city(profile.city) == order_city
    ]

    if not candidates:
        order.worker_id = None
        order.status = OrderStatus.PENDING
        order.assigned_at = None
        return None

    candidates.sort(key=lambda item: (-item[0].rating_avg, -item[0].completed_orders, item[1].created_at))
    profile, worker = candidates[0]
    profile.availability = WorkerAvailability.BUSY
    order.worker_id = worker.id
    order.status = OrderStatus.ASSIGNED
    order.assigned_at = utc_now()
    return worker


async def assign_next_pending_order_to_worker(session: AsyncSession, worker: User) -> Order | None:
    profile = await session.get(WorkerProfile, worker.id)
    if worker.role != UserRole.WORKER or profile is None or profile.availability != WorkerAvailability.AVAILABLE:
        return None

    worker_city = normalize_city(profile.city)
    if worker_city is None:
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

    orders = list(
        (
            await session.execute(
                select(Order)
                .where(Order.status == OrderStatus.PENDING)
                .where(Order.worker_id.is_(None))
                .where(Order.city.is_not(None))
                .order_by(Order.created_at.asc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    matching_orders = [order for order in orders if normalize_city(order.city) == worker_city]
    if not matching_orders:
        return None

    order = matching_orders[0]
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
