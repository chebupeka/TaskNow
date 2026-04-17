from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole, WorkerProfile
from app.schemas.auth import (
    AvatarUpdateRequest,
    IdentityVerificationRequest,
    LoginRequest,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.users import UserRead, WorkerRead

router = APIRouter(prefix="/auth", tags=["auth"])

ADMIN_LOGIN = "admin"
ADMIN_EMAIL = "admin@tasknow.local"
ADMIN_PASSWORD = "admin"


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def build_auth_user(db: AsyncSession, user: User) -> UserRead | WorkerRead:
    if user.role == UserRole.WORKER:
        profile = await db.get(WorkerProfile, user.id)
        if profile is not None:
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
                city=profile.city,
                current_lat=profile.current_lat,
                current_lng=profile.current_lng,
            )

    return UserRead.model_validate(user)


async def make_token_response(db: AsyncSession, user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        user=await build_auth_user(db, user),
    )


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    normalized_email = normalize_email(email)
    if normalized_email == ADMIN_LOGIN and password == ADMIN_PASSWORD:
        user = (
            await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        ).scalar_one_or_none()
        if user is None:
            user = User(
                role=UserRole.ADMIN,
                full_name="TaskNow Admin",
                email=ADMIN_EMAIL,
                phone=None,
                hashed_password=hash_password(ADMIN_PASSWORD),
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        else:
            user.role = UserRole.ADMIN
            user.full_name = user.full_name or "TaskNow Admin"
            user.hashed_password = hash_password(ADMIN_PASSWORD)
            user.is_active = True
            await db.commit()
            await db.refresh(user)
        return user

    user = (
        await db.execute(select(User).where(User.email == normalized_email))
    ).scalar_one_or_none()

    if user is None or user.hashed_password is None or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь отключен",
        )

    return user


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    if payload.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Регистрация администратора через публичный API запрещена",
        )

    user = User(
        role=payload.role,
        full_name=payload.full_name,
        phone=payload.phone,
        email=normalize_email(payload.email),
        hashed_password=hash_password(payload.password),
    )
    db.add(user)

    try:
        await db.flush()
        if payload.role == UserRole.WORKER:
            db.add(
                WorkerProfile(
                    user_id=user.id,
                    skills=payload.skills,
                    city=payload.city,
                    current_lat=payload.current_lat,
                    current_lng=payload.current_lng,
                )
            )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким телефоном или email уже существует",
        ) from exc

    await db.refresh(user)
    return await make_token_response(db, user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await authenticate_user(db, payload.email, payload.password)
    return await make_token_response(db, user)


@router.post("/token", response_model=TokenResponse)
async def login_for_swagger(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user = await authenticate_user(db, form_data.username, form_data.password)
    return await make_token_response(db, user)


@router.get("/me", response_model=UserRead | WorkerRead)
async def read_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead | WorkerRead:
    return await build_auth_user(db, current_user)


@router.put("/me/profile", response_model=UserRead | WorkerRead)
async def update_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead | WorkerRead:
    current_user.full_name = payload.full_name
    current_user.email = normalize_email(payload.email)
    current_user.phone = payload.phone
    if current_user.role == UserRole.WORKER:
        profile = await db.get(WorkerProfile, current_user.id)
        if profile is not None:
            profile.city = payload.city

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким телефоном или email уже существует",
        ) from exc

    await db.refresh(current_user)
    return await build_auth_user(db, current_user)


@router.put("/me/password", response_model=UserRead | WorkerRead)
async def change_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead | WorkerRead:
    if current_user.hashed_password is None or not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Текущий пароль указан неверно")

    current_user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    await db.refresh(current_user)
    return await build_auth_user(db, current_user)


@router.put("/me/avatar", response_model=UserRead | WorkerRead)
async def update_avatar(
    payload: AvatarUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead | WorkerRead:
    current_user.avatar_url = str(payload.avatar_url) if payload.avatar_url else None
    await db.commit()
    await db.refresh(current_user)
    return await build_auth_user(db, current_user)


@router.post("/me/identity", response_model=UserRead | WorkerRead)
async def verify_identity(
    payload: IdentityVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead | WorkerRead:
    current_user.passport_full_name = payload.passport_full_name
    current_user.passport_number = payload.passport_number
    current_user.identity_status = "verified"
    await db.commit()
    await db.refresh(current_user)
    return await build_auth_user(db, current_user)
