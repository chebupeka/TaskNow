from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User, UserRole, WorkerAvailability, WorkerProfile
from app.models.order import Order, OrderStatus
from app.models.review import Review
from app.schemas.orders import ReviewRead
from app.schemas.users import WorkerCreate, WorkerRead
from app.services.assignment import assign_next_pending_order_to_worker

router = APIRouter(prefix="/workers", tags=["workers"])


def build_worker_read(user: User, profile: WorkerProfile) -> WorkerRead:
    return WorkerRead(
        id=user.id,
        role=user.role,
        full_name=user.full_name,
        phone=user.phone,
        email=user.email,
        avatar_url=user.avatar_url,
        identity_status=user.identity_status,
        skills=profile.skills,
        availability=profile.availability,
        rating_avg=profile.rating_avg,
        rating_count=profile.rating_count,
        completed_orders=profile.completed_orders,
        current_lat=profile.current_lat,
        current_lng=profile.current_lng,
    )


@router.post("", response_model=WorkerRead, status_code=status.HTTP_201_CREATED)
async def create_worker(payload: WorkerCreate, db: AsyncSession = Depends(get_db)) -> WorkerRead:
    worker = User(
        role=UserRole.WORKER,
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
    )
    db.add(worker)

    try:
        await db.flush()
        profile = WorkerProfile(
            user_id=worker.id,
            skills=payload.skills,
            current_lat=payload.current_lat,
            current_lng=payload.current_lng,
        )
        db.add(profile)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Работник с таким телефоном или email уже существует",
        ) from exc

    return build_worker_read(worker, profile)


@router.get("", response_model=list[WorkerRead])
async def list_workers(
    available_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[WorkerRead]:
    statement = (
        select(User, WorkerProfile)
        .join(WorkerProfile, WorkerProfile.user_id == User.id)
        .where(User.role == UserRole.WORKER)
        .order_by(WorkerProfile.rating_avg.desc(), User.created_at.asc())
    )

    if available_only:
        statement = statement.where(WorkerProfile.availability == WorkerAvailability.AVAILABLE)

    rows = (await db.execute(statement)).all()
    return [build_worker_read(user, profile) for user, profile in rows]


@router.get("/me", response_model=WorkerRead)
async def get_my_worker_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkerRead:
    profile = await db.get(WorkerProfile, current_user.id)
    if current_user.role != UserRole.WORKER or profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Профиль работника не найден")

    return build_worker_read(current_user, profile)


@router.get("/me/reviews", response_model=list[ReviewRead])
async def list_my_worker_reviews(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Review]:
    if current_user.role != UserRole.WORKER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Отзывы доступны только работнику")
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


@router.post("/me/availability", response_model=WorkerRead)
async def set_my_worker_availability(
    availability: WorkerAvailability,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkerRead:
    profile = await db.get(WorkerProfile, current_user.id)
    if current_user.role != UserRole.WORKER or profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Профиль работника не найден")

    if availability == WorkerAvailability.OFFLINE:
        active_order_id = (
            await db.execute(
                select(Order.id)
                .where(Order.worker_id == current_user.id)
                .where(
                    Order.status.in_(
                        [
                            OrderStatus.ACCEPTED,
                            OrderStatus.IN_PROGRESS,
                            OrderStatus.COMPLETION_REQUESTED,
                        ]
                    )
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if active_order_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Нельзя завершить смену, пока есть активная задача",
            )

        assigned_orders = (
            await db.execute(
                select(Order)
                .where(Order.worker_id == current_user.id)
                .where(Order.status == OrderStatus.ASSIGNED)
            )
        ).scalars().all()
        for order in assigned_orders:
            order.worker_id = None
            order.status = OrderStatus.PENDING
            order.assigned_at = None

    profile.availability = availability
    if availability == WorkerAvailability.AVAILABLE:
        await assign_next_pending_order_to_worker(db, current_user)
    await db.commit()
    await db.refresh(profile)
    return build_worker_read(current_user, profile)


@router.post("/{worker_id}/availability", response_model=WorkerRead)
async def set_worker_availability(
    worker_id: UUID,
    availability: WorkerAvailability,
    db: AsyncSession = Depends(get_db),
) -> WorkerRead:
    worker = await db.get(User, worker_id)
    profile = await db.get(WorkerProfile, worker_id)

    if worker is None or profile is None or worker.role != UserRole.WORKER:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Работник не найден")

    profile.availability = availability
    await db.commit()
    return build_worker_read(worker, profile)
