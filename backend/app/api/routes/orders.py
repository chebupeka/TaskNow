from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.notification import Notification, NotificationKind
from app.models.message import ChatMessage
from app.models.order import Order, OrderStatus
from app.models.review import Review
from app.models.user import User, UserRole, WorkerAvailability, WorkerProfile, utc_now
from app.schemas.orders import (
    OrderCreate,
    OrderCreateForCurrentUser,
    OrderRead,
    ReviewCreate,
    ReviewCreateForCurrentUser,
    ReviewRead,
    WorkerOrderAction,
)
from app.services.assignment import assign_best_worker
from app.services.payments import create_pending_payment, dispute_payment_for_order, hold_payment_for_order, release_payment_to_worker, reset_payment_assignment
from app.services.rating import apply_worker_review

router = APIRouter(prefix="/orders", tags=["orders"])

COMPLETED_ORDER_STATUSES = {OrderStatus.COMPLETED, OrderStatus.REVIEWED, OrderStatus.CANCELED}
VISIBLE_DONE_ORDER_STATUSES = COMPLETED_ORDER_STATUSES | {OrderStatus.DISPUTED}
COMPLETED_ORDERS_LIMIT = 8
DISPUTE_ADMIN_EMAIL = "admin@tasknow.local"


def create_notification(
    user_id: UUID,
    kind: NotificationKind,
    title: str,
    body: str,
    order_id: UUID | None = None,
) -> Notification:
    return Notification(
        user_id=user_id,
        order_id=order_id,
        kind=kind,
        title=title,
        body=body,
    )


async def get_order_or_404(db: AsyncSession, order_id: UUID) -> Order:
    order = await db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")
    return order


async def require_worker_profile(db: AsyncSession, worker_id: UUID) -> WorkerProfile:
    profile = await db.get(WorkerProfile, worker_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Профиль работника не найден")
    return profile


def require_role(user: User, role: UserRole) -> None:
    if user.role != role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Требуется роль {role.value}",
        )


async def mark_order_notifications_read(
    db: AsyncSession,
    user_id: UUID,
    order_id: UUID,
    kinds: set[NotificationKind] | None = None,
) -> None:
    statement = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .where(Notification.order_id == order_id)
        .where(Notification.is_read.is_(False))
    )
    if kinds:
        statement = statement.where(Notification.kind.in_(kinds))

    notifications = (await db.execute(statement)).scalars().all()
    for notification in notifications:
        notification.is_read = True


async def get_or_create_dispute_admin(db: AsyncSession) -> User:
    admin = (
        await db.execute(select(User).where(User.email == DISPUTE_ADMIN_EMAIL))
    ).scalar_one_or_none()
    if admin is None:
        admin = User(
            role=UserRole.ADMIN,
            full_name="TaskNow Dispute Admin",
            email=DISPUTE_ADMIN_EMAIL,
            phone=None,
            hashed_password=None,
        )
        db.add(admin)
        await db.flush()
    return admin


async def add_dispute_admin_message(db: AsyncSession, order: Order) -> None:
    admin = await get_or_create_dispute_admin(db)
    existing_admin_message = (
        await db.execute(
            select(ChatMessage)
            .where(ChatMessage.order_id == order.id)
            .where(ChatMessage.sender_id == admin.id)
            .where(ChatMessage.client_message_id == "dispute-admin-joined")
        )
    ).scalar_one_or_none()
    if existing_admin_message is not None:
        return

    db.add(
        ChatMessage(
            order_id=order.id,
            sender_id=admin.id,
            body="Администратор подключился к спору. Платеж остается замороженным до решения вопроса.",
            client_message_id="dispute-admin-joined",
        )
    )


async def enrich_orders_with_worker_info(db: AsyncSession, orders: list[Order]) -> list[Order]:
    user_ids = {order.customer_id for order in orders}
    user_ids.update(order.worker_id for order in orders if order.worker_id is not None)
    if not user_ids:
        return orders

    users = {
        user.id: user
        for user in (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
    }
    worker_ids = {order.worker_id for order in orders if order.worker_id is not None}
    profiles = {
        profile.user_id: profile
        for profile in (await db.execute(select(WorkerProfile).where(WorkerProfile.user_id.in_(worker_ids)))).scalars().all()
    } if worker_ids else {}

    for order in orders:
        customer = users.get(order.customer_id)
        order.customer_full_name = customer.full_name if customer else None
        order.customer_avatar_url = customer.avatar_url if customer else None
        if order.worker_id is None:
            continue
        user = users.get(order.worker_id)
        profile = profiles.get(order.worker_id)
        order.worker_full_name = user.full_name if user else None
        order.worker_avatar_url = user.avatar_url if user else None
        order.worker_rating_avg = profile.rating_avg if profile else None
        order.worker_rating_count = profile.rating_count if profile else None
    return orders


async def enrich_order_with_worker_info(db: AsyncSession, order: Order) -> Order:
    return (await enrich_orders_with_worker_info(db, [order]))[0]


async def prune_completed_orders_for_user(db: AsyncSession, user: User) -> None:
    statement = (
        select(Order.id)
        .where(Order.status.in_(COMPLETED_ORDER_STATUSES))
        .order_by(Order.completed_at.desc(), Order.updated_at.desc(), Order.created_at.desc())
        .offset(COMPLETED_ORDERS_LIMIT)
    )

    if user.role == UserRole.CUSTOMER:
        statement = statement.where(Order.customer_id == user.id)
    elif user.role == UserRole.WORKER:
        statement = statement.where(Order.worker_id == user.id)
    else:
        return

    stale_order_ids = list((await db.execute(statement)).scalars().all())
    if stale_order_ids:
        await db.execute(delete(Order).where(Order.id.in_(stale_order_ids)))
        await db.commit()


async def create_order_for_customer(
    db: AsyncSession,
    customer: User,
    payload: OrderCreateForCurrentUser,
) -> Order:
    order = Order(
        customer_id=customer.id,
        description=payload.description,
        budget_amount=payload.budget_amount,
        city=payload.city,
        address=payload.address,
        scheduled_at=payload.scheduled_at,
        status=OrderStatus.PENDING,
    )
    db.add(order)
    await db.flush()
    await create_pending_payment(db, order)

    worker = await assign_best_worker(db, order)
    if worker is None:
        db.add(
            create_notification(
                user_id=customer.id,
                order_id=order.id,
                kind=NotificationKind.ORDER_PENDING,
                title="Заказ создан",
                body="Свободный работник пока не найден. Заказ ожидает назначения.",
            )
        )
    else:
        db.add_all(
            [
                create_notification(
                    user_id=worker.id,
                    order_id=order.id,
                    kind=NotificationKind.ORDER_ASSIGNED,
                    title="Новый заказ",
                    body=f"{order.address}: {order.description[:120]}",
                ),
                create_notification(
                    user_id=customer.id,
                    order_id=order.id,
                    kind=NotificationKind.ORDER_ASSIGNED,
                    title="Исполнитель назначен",
                    body=f"Заказ передан работнику {worker.full_name}.",
                ),
            ]
        )

    await db.commit()
    await db.refresh(order)
    return await enrich_order_with_worker_info(db, order)


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(payload: OrderCreate, db: AsyncSession = Depends(get_db)) -> Order:
    customer = await db.get(User, payload.customer_id)
    if customer is None or customer.role != UserRole.CUSTOMER:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказчик не найден")

    return await create_order_for_customer(
        db,
        customer,
        OrderCreateForCurrentUser(
            description=payload.description,
            budget_amount=payload.budget_amount,
            city=payload.city,
            address=payload.address,
            scheduled_at=payload.scheduled_at,
        ),
    )


@router.post("/me", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_my_order(
    payload: OrderCreateForCurrentUser,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Order:
    require_role(current_user, UserRole.CUSTOMER)
    return await create_order_for_customer(db, current_user, payload)


@router.get("", response_model=list[OrderRead])
async def list_orders(
    customer_id: UUID | None = None,
    worker_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[Order]:
    statement = select(Order).order_by(Order.created_at.desc()).limit(100)

    if customer_id:
        statement = statement.where(Order.customer_id == customer_id)
    if worker_id:
        statement = statement.where(Order.worker_id == worker_id)

    return await enrich_orders_with_worker_info(db, list((await db.execute(statement)).scalars().all()))


@router.get("/me", response_model=list[OrderRead])
async def list_my_orders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Order]:
    await prune_completed_orders_for_user(db, current_user)
    statement = select(Order).order_by(Order.created_at.desc()).limit(100)

    if current_user.role == UserRole.CUSTOMER:
        statement = statement.where(Order.customer_id == current_user.id)
    elif current_user.role == UserRole.WORKER:
        profile = await db.get(WorkerProfile, current_user.id)
        if profile is None or profile.availability == WorkerAvailability.OFFLINE:
            statement = statement.where(Order.worker_id == current_user.id).where(
                Order.status.in_(VISIBLE_DONE_ORDER_STATUSES)
            )
        else:
            statement = statement.where(Order.worker_id == current_user.id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Для администратора используйте общий список заказов",
        )

    return await enrich_orders_with_worker_info(db, list((await db.execute(statement)).scalars().all()))


@router.get("/me/{order_id}", response_model=OrderRead)
async def get_my_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Order:
    order = await get_order_or_404(db, order_id)
    if order.customer_id != current_user.id and order.worker_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к заказу")
    return await enrich_order_with_worker_info(db, order)


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(order_id: UUID, db: AsyncSession = Depends(get_db)) -> Order:
    return await enrich_order_with_worker_info(db, await get_order_or_404(db, order_id))


@router.post("/{order_id}/accept", response_model=OrderRead)
async def accept_order(
    order_id: UUID,
    payload: WorkerOrderAction,
    db: AsyncSession = Depends(get_db),
) -> Order:
    order = await get_order_or_404(db, order_id)
    await require_worker_profile(db, payload.worker_id)

    if order.worker_id != payload.worker_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Заказ назначен другому работнику")
    if order.status != OrderStatus.ASSIGNED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Заказ нельзя принять в текущем статусе")

    order.status = OrderStatus.ACCEPTED
    order.decision_at = utc_now()
    await hold_payment_for_order(db, order)
    await mark_order_notifications_read(
        db,
        payload.worker_id,
        order.id,
        {NotificationKind.ORDER_ASSIGNED, NotificationKind.ORDER_REASSIGNED},
    )
    db.add(
        create_notification(
            user_id=order.customer_id,
            order_id=order.id,
            kind=NotificationKind.ORDER_ACCEPTED,
            title="Заказ принят",
            body="Работник подтвердил выполнение заказа.",
        )
    )

    await db.commit()
    await db.refresh(order)
    return await enrich_order_with_worker_info(db, order)


@router.post("/{order_id}/accept/me", response_model=OrderRead)
async def accept_my_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Order:
    require_role(current_user, UserRole.WORKER)
    return await accept_order(order_id, WorkerOrderAction(worker_id=current_user.id), db)


@router.post("/{order_id}/decline", response_model=OrderRead)
async def decline_order(
    order_id: UUID,
    payload: WorkerOrderAction,
    db: AsyncSession = Depends(get_db),
) -> Order:
    order = await get_order_or_404(db, order_id)
    profile = await require_worker_profile(db, payload.worker_id)

    if order.worker_id != payload.worker_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Заказ назначен другому работнику")
    if order.status != OrderStatus.ASSIGNED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Заказ нельзя отклонить в текущем статусе")

    profile.availability = WorkerAvailability.AVAILABLE
    order.worker_id = None
    order.status = OrderStatus.PENDING
    order.decision_at = utc_now()
    await reset_payment_assignment(db, order)

    next_worker = await assign_best_worker(db, order, exclude_worker_ids={payload.worker_id})
    if next_worker is None:
        db.add(
            create_notification(
                user_id=order.customer_id,
                order_id=order.id,
                kind=NotificationKind.ORDER_DECLINED,
                title="Работник отклонил заказ",
                body="Заказ снова ожидает свободного исполнителя.",
            )
        )
    else:
        db.add_all(
            [
                create_notification(
                    user_id=next_worker.id,
                    order_id=order.id,
                    kind=NotificationKind.ORDER_REASSIGNED,
                    title="Новый заказ",
                    body=f"{order.address}: {order.description[:120]}",
                ),
                create_notification(
                    user_id=order.customer_id,
                    order_id=order.id,
                    kind=NotificationKind.ORDER_REASSIGNED,
                    title="Назначен другой исполнитель",
                    body=f"Заказ передан работнику {next_worker.full_name}.",
                ),
            ]
        )

    await db.commit()
    await db.refresh(order)
    return await enrich_order_with_worker_info(db, order)


@router.post("/{order_id}/decline/me", response_model=OrderRead)
async def decline_my_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Order:
    require_role(current_user, UserRole.WORKER)
    return await decline_order(order_id, WorkerOrderAction(worker_id=current_user.id), db)


@router.post("/{order_id}/start", response_model=OrderRead)
async def start_order(
    order_id: UUID,
    payload: WorkerOrderAction,
    db: AsyncSession = Depends(get_db),
) -> Order:
    order = await get_order_or_404(db, order_id)

    if order.worker_id != payload.worker_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Заказ назначен другому работнику")
    if order.status != OrderStatus.ACCEPTED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Сначала нужно принять заказ")

    order.status = OrderStatus.IN_PROGRESS
    order.started_at = utc_now()
    await db.commit()
    await db.refresh(order)
    return await enrich_order_with_worker_info(db, order)


@router.post("/{order_id}/start/me", response_model=OrderRead)
async def start_my_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Order:
    require_role(current_user, UserRole.WORKER)
    return await start_order(order_id, WorkerOrderAction(worker_id=current_user.id), db)


@router.post("/{order_id}/complete", response_model=OrderRead)
async def request_order_completion(
    order_id: UUID,
    payload: WorkerOrderAction,
    db: AsyncSession = Depends(get_db),
) -> Order:
    order = await get_order_or_404(db, order_id)
    await require_worker_profile(db, payload.worker_id)

    if order.worker_id != payload.worker_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Заказ назначен другому работнику")
    if order.status != OrderStatus.IN_PROGRESS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Заказ не находится в работе")

    order.status = OrderStatus.COMPLETION_REQUESTED
    db.add(
        create_notification(
            user_id=order.customer_id,
            order_id=order.id,
            kind=NotificationKind.ORDER_COMPLETION_REQUESTED,
            title="Работник просит подтвердить завершение",
            body="Проверьте результат и подтвердите выполнение задачи.",
        )
    )

    await db.commit()
    await db.refresh(order)
    return await enrich_order_with_worker_info(db, order)


@router.post("/{order_id}/complete/me", response_model=OrderRead)
async def request_my_order_completion(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Order:
    require_role(current_user, UserRole.WORKER)
    return await request_order_completion(order_id, WorkerOrderAction(worker_id=current_user.id), db)


async def confirm_order_completion_by_customer(
    order_id: UUID,
    customer: User,
    db: AsyncSession,
) -> Order:
    order = await get_order_or_404(db, order_id)
    if order.customer_id != customer.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Подтвердить заказ может только заказчик")
    if order.worker_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="У заказа нет назначенного работника")
    if order.status != OrderStatus.COMPLETION_REQUESTED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Работник еще не отправил запрос на завершение")

    profile = await require_worker_profile(db, order.worker_id)
    order.status = OrderStatus.COMPLETED
    order.completed_at = utc_now()
    profile.availability = WorkerAvailability.AVAILABLE
    await release_payment_to_worker(db, order)
    await db.execute(delete(ChatMessage).where(ChatMessage.order_id == order.id))
    await mark_order_notifications_read(
        db,
        customer.id,
        order.id,
        {NotificationKind.ORDER_COMPLETION_REQUESTED},
    )
    db.add_all(
        [
            create_notification(
                user_id=order.worker_id,
                order_id=order.id,
                kind=NotificationKind.ORDER_COMPLETED,
                title="Заказчик подтвердил завершение",
                body="Задача завершена. Спасибо за работу.",
            ),
            create_notification(
                user_id=order.customer_id,
                order_id=order.id,
                kind=NotificationKind.ORDER_READY_TO_REVIEW,
                title="Задача завершена",
                body="Теперь можно оставить отзыв исполнителю.",
            ),
        ]
    )

    await db.commit()
    await db.refresh(order)
    return await enrich_order_with_worker_info(db, order)


@router.post("/{order_id}/confirm-complete/me", response_model=OrderRead)
async def confirm_my_order_completion(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Order:
    require_role(current_user, UserRole.CUSTOMER)
    return await confirm_order_completion_by_customer(order_id, current_user, db)


@router.post("/{order_id}/dispute/me", response_model=OrderRead)
async def open_my_order_dispute(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Order:
    order = await get_order_or_404(db, order_id)
    if order.customer_id != current_user.id and order.worker_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к заказу")
    if order.status not in {OrderStatus.ACCEPTED, OrderStatus.IN_PROGRESS, OrderStatus.COMPLETION_REQUESTED}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Спор можно открыть только по активному заказу")

    order.status = OrderStatus.DISPUTED
    await dispute_payment_for_order(db, order)
    if order.worker_id is not None:
        profile = await db.get(WorkerProfile, order.worker_id)
        if profile is not None:
            profile.availability = WorkerAvailability.AVAILABLE
    await add_dispute_admin_message(db, order)
    if order.worker_id is not None:
        db.add(
            create_notification(
                user_id=order.worker_id if current_user.id == order.customer_id else order.customer_id,
                order_id=order.id,
                kind=NotificationKind.ORDER_COMPLETED,
                title="Открыт спор по заказу",
                body="Платеж заморожен до решения спора.",
            )
        )
    await db.commit()
    await db.refresh(order)
    return await enrich_order_with_worker_info(db, order)


@router.post("/{order_id}/review", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
async def review_order(
    order_id: UUID,
    payload: ReviewCreate,
    db: AsyncSession = Depends(get_db),
) -> Review:
    order = await get_order_or_404(db, order_id)

    if order.customer_id != payload.customer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Оценку может поставить только заказчик")
    if order.worker_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="У заказа нет назначенного работника")
    if order.status not in {OrderStatus.COMPLETED, OrderStatus.REVIEWED}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Оценить можно только завершенную задачу")

    existing_review = (
        await db.execute(select(Review).where(Review.order_id == order.id))
    ).scalar_one_or_none()
    if existing_review is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Заказ уже оценен")

    review = Review(
        order_id=order.id,
        customer_id=order.customer_id,
        worker_id=order.worker_id,
        score=payload.score,
        comment=payload.comment,
    )
    db.add(review)
    await apply_worker_review(db, order.worker_id, payload.score)
    order.status = OrderStatus.REVIEWED
    await mark_order_notifications_read(
        db,
        order.customer_id,
        order.id,
        {NotificationKind.ORDER_READY_TO_REVIEW},
    )
    db.add(
        create_notification(
            user_id=order.worker_id,
            order_id=order.id,
            kind=NotificationKind.REVIEW_RECEIVED,
            title="Получена оценка",
            body=f"Заказчик поставил {payload.score} из 5.",
        )
    )

    await db.commit()
    await db.refresh(review)
    return review


@router.get("/reviews/me", response_model=list[ReviewRead])
async def list_my_worker_reviews(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Review]:
    require_role(current_user, UserRole.WORKER)
    reviews = list(
        (
            await db.execute(
                select(Review)
                .where(Review.worker_id == current_user.id)
                .order_by(Review.created_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    if not reviews:
        return reviews

    order_ids = {review.order_id for review in reviews}
    customer_ids = {review.customer_id for review in reviews}
    orders = {
        order.id: order
        for order in (await db.execute(select(Order).where(Order.id.in_(order_ids)))).scalars().all()
    }
    customers = {
        user.id: user
        for user in (await db.execute(select(User).where(User.id.in_(customer_ids)))).scalars().all()
    }
    for review in reviews:
        order = orders.get(review.order_id)
        customer = customers.get(review.customer_id)
        review.order_title = order.description.split(".")[0] if order else None
        review.customer_full_name = customer.full_name if customer else None
    return reviews


@router.post("/{order_id}/review/me", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
async def review_my_order(
    order_id: UUID,
    payload: ReviewCreateForCurrentUser,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Review:
    require_role(current_user, UserRole.CUSTOMER)
    return await review_order(
        order_id,
        ReviewCreate(
            customer_id=current_user.id,
            score=payload.score,
            comment=payload.comment,
        ),
        db,
    )
