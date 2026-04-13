from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.order import Order
from app.models.payment import Payment, PaymentStatus, Payout
from app.models.user import User, UserRole
from app.schemas.payments import PaymentsDashboard, PaymentRead, PayoutRead, WalletRead
from app.services.payments import calculate_service_fee, calculate_worker_amount, get_or_create_wallet, pay_out_wallet

router = APIRouter(prefix="/payments", tags=["payments"])


def get_order_title(description: str) -> str:
    return description.split(".")[0] or "Задача"


async def enrich_payment_titles(db: AsyncSession, payments: list[Payment]) -> list[Payment]:
    order_ids = {payment.order_id for payment in payments}
    if not order_ids:
        return payments
    orders = {
        order.id: order
        for order in (await db.execute(select(Order).where(Order.id.in_(order_ids)))).scalars().all()
    }
    for payment in payments:
        order = orders.get(payment.order_id)
        if order is None:
            payment.order_title = None
            continue
        payment.order_title = get_order_title(order.description)
        expected_service_fee = calculate_service_fee(payment.amount)
        expected_worker_amount = calculate_worker_amount(payment.amount)
        if payment.service_fee != expected_service_fee or payment.worker_amount != expected_worker_amount:
            payment.service_fee = expected_service_fee
            payment.worker_amount = expected_worker_amount
    return payments


@router.get("/me", response_model=PaymentsDashboard)
async def get_my_payments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentsDashboard:
    wallet = await get_or_create_wallet(db, current_user.id)
    payment_statement = select(Payment).order_by(Payment.created_at.desc()).limit(50)
    payout_statement = select(Payout).where(Payout.worker_id == current_user.id).order_by(Payout.created_at.desc()).limit(20)

    if current_user.role == UserRole.CUSTOMER:
        payment_statement = payment_statement.where(Payment.customer_id == current_user.id)
        payouts: list[Payout] = []
    elif current_user.role == UserRole.WORKER:
        payment_statement = payment_statement.where(Payment.worker_id == current_user.id)
        payouts = list((await db.execute(payout_statement)).scalars().all())
    else:
        payment_statement = payment_statement.where(Payment.customer_id == current_user.id)
        payouts = []

    payments = await enrich_payment_titles(db, list((await db.execute(payment_statement)).scalars().all()))
    held_payments = [payment for payment in payments if payment.status in {PaymentStatus.HELD, PaymentStatus.DISPUTED}]
    hold_total = sum(
        payment.worker_amount if current_user.role == UserRole.WORKER else payment.amount
        for payment in held_payments
    )

    return PaymentsDashboard(
        wallet=WalletRead.model_validate(wallet),
        payments=[PaymentRead.model_validate(payment) for payment in payments],
        payouts=[PayoutRead.model_validate(payout) for payout in payouts],
        hold_total=hold_total,
    )


@router.post("/me/payout", response_model=PayoutRead, status_code=status.HTTP_201_CREATED)
async def request_my_payout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Payout:
    if current_user.role != UserRole.WORKER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Вывод доступен только работнику")
    payout = await pay_out_wallet(db, current_user.id)
    if payout is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Нет доступных средств для вывода")
    await db.commit()
    await db.refresh(payout)
    return payout
