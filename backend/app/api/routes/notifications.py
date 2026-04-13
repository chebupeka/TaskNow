from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notifications import NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"])
MAX_VISIBLE_NOTIFICATIONS = 4


async def prune_old_notifications(db: AsyncSession, user_id: UUID, unread_only: bool = False) -> None:
    keep_statement = (
        select(Notification.id)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(MAX_VISIBLE_NOTIFICATIONS)
    )
    if unread_only:
        keep_statement = keep_statement.where(Notification.is_read.is_(False))

    keep_ids = list((await db.execute(keep_statement)).scalars().all())
    delete_statement = delete(Notification).where(Notification.user_id == user_id)
    if unread_only:
        delete_statement = delete_statement.where(Notification.is_read.is_(False))
    if keep_ids:
        delete_statement = delete_statement.where(Notification.id.notin_(keep_ids))

    await db.execute(delete_statement)
    await db.commit()


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    user_id: UUID,
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[Notification]:
    await prune_old_notifications(db, user_id, unread_only)
    statement = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(MAX_VISIBLE_NOTIFICATIONS)
    )

    if unread_only:
        statement = statement.where(Notification.is_read.is_(False))

    return list((await db.execute(statement)).scalars().all())


@router.get("/me", response_model=list[NotificationRead])
async def list_my_notifications(
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Notification]:
    await prune_old_notifications(db, current_user.id, unread_only)
    statement = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(MAX_VISIBLE_NOTIFICATIONS)
    )

    if unread_only:
        statement = statement.where(Notification.is_read.is_(False))

    return list((await db.execute(statement)).scalars().all())


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Notification:
    notification = await db.get(Notification, notification_id)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Уведомление не найдено")

    notification.is_read = True
    await db.commit()
    await db.refresh(notification)
    return notification


@router.post("/{notification_id}/read/me", response_model=NotificationRead)
async def mark_my_notification_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Notification:
    notification = await db.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Уведомление не найдено")

    notification.is_read = True
    await db.commit()
    await db.refresh(notification)
    return notification
