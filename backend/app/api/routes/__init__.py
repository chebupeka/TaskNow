from fastapi import APIRouter

from app.api.routes import admin, auth, customers, health, messages, notifications, orders, payments, workers

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(customers.router)
api_router.include_router(workers.router)
api_router.include_router(orders.router)
api_router.include_router(messages.router)
api_router.include_router(payments.router)
api_router.include_router(notifications.router)
