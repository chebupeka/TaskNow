from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.user import User, UserRole
from app.schemas.users import CustomerCreate, UserRead

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_customer(payload: CustomerCreate, db: AsyncSession = Depends(get_db)) -> User:
    customer = User(
        role=UserRole.CUSTOMER,
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
    )
    db.add(customer)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким телефоном или email уже существует",
        ) from exc

    await db.refresh(customer)
    return customer
