from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.payment import Payment, PaymentStatus, Payout, Wallet

SERVICE_FEE_PERCENT = 10


def calculate_service_fee(amount: int) -> int:
    return max(0, round(amount * SERVICE_FEE_PERCENT / 100))


def calculate_worker_amount(amount: int) -> int:
    return max(0, amount - calculate_service_fee(amount))


def sync_payment_amounts(payment: Payment, amount: int) -> None:
    payment.amount = amount
    payment.service_fee = calculate_service_fee(amount)
    payment.worker_amount = calculate_worker_amount(amount)


async def get_or_create_wallet(db: AsyncSession, user_id: UUID) -> Wallet:
    wallet = await db.get(Wallet, user_id)
    if wallet is None:
        wallet = Wallet(user_id=user_id)
        db.add(wallet)
        await db.flush()
    return wallet


async def get_or_create_payment(db: AsyncSession, order: Order) -> Payment:
    payment = (
        await db.execute(select(Payment).where(Payment.order_id == order.id))
    ).scalar_one_or_none()
    if payment is None:
        payment = Payment(
            order_id=order.id,
            customer_id=order.customer_id,
            worker_id=order.worker_id,
            amount=order.budget_amount,
            service_fee=calculate_service_fee(order.budget_amount),
            worker_amount=calculate_worker_amount(order.budget_amount),
            status=PaymentStatus.PENDING,
        )
        db.add(payment)
        await db.flush()
    else:
        expected_service_fee = calculate_service_fee(order.budget_amount)
        expected_worker_amount = calculate_worker_amount(order.budget_amount)
        if (
            payment.amount != order.budget_amount
            or payment.service_fee != expected_service_fee
            or payment.worker_amount != expected_worker_amount
        ):
            sync_payment_amounts(payment, order.budget_amount)
    return payment


async def create_pending_payment(db: AsyncSession, order: Order) -> Payment:
    payment = Payment(
        order_id=order.id,
        customer_id=order.customer_id,
        worker_id=order.worker_id,
        amount=order.budget_amount,
        service_fee=calculate_service_fee(order.budget_amount),
        worker_amount=calculate_worker_amount(order.budget_amount),
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    await db.flush()
    return payment


async def hold_payment_for_order(db: AsyncSession, order: Order) -> Payment:
    payment = await get_or_create_payment(db, order)
    payment.worker_id = order.worker_id
    sync_payment_amounts(payment, order.budget_amount)
    payment.status = PaymentStatus.HELD
    return payment


async def reset_payment_assignment(db: AsyncSession, order: Order) -> Payment:
    payment = await get_or_create_payment(db, order)
    payment.worker_id = None
    payment.status = PaymentStatus.PENDING
    return payment


async def release_payment_to_worker(db: AsyncSession, order: Order) -> Payment:
    payment = await get_or_create_payment(db, order)
    if payment.status == PaymentStatus.RELEASED:
        return payment
    payment.worker_id = order.worker_id
    payment.status = PaymentStatus.RELEASED
    if order.worker_id is not None:
        wallet = await get_or_create_wallet(db, order.worker_id)
        wallet.balance_available += payment.worker_amount
    return payment


async def dispute_payment_for_order(db: AsyncSession, order: Order) -> Payment:
    payment = await get_or_create_payment(db, order)
    payment.worker_id = order.worker_id
    sync_payment_amounts(payment, order.budget_amount)
    payment.status = PaymentStatus.DISPUTED
    return payment


async def pay_out_wallet(db: AsyncSession, worker_id: UUID) -> Payout | None:
    wallet = await get_or_create_wallet(db, worker_id)
    if wallet.balance_available <= 0:
        return None
    amount = wallet.balance_available
    wallet.balance_available = 0
    wallet.balance_paid_out += amount
    payout = Payout(worker_id=worker_id, amount=amount)
    db.add(payout)
    return payout
