from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine


async def ensure_local_schema_columns() -> None:
    async with engine.begin() as connection:
        dialect = connection.dialect.name
        if dialect == "sqlite":
            rows = await connection.execute(text("pragma table_info(users)"))
            existing_columns = {row[1] for row in rows}
            columns = {
                "avatar_url": "text",
                "identity_status": "varchar(32) not null default 'not_verified'",
                "passport_full_name": "varchar(160)",
                "passport_number": "varchar(32)",
            }
            for name, definition in columns.items():
                if name not in existing_columns:
                    await connection.execute(text(f"alter table users add column {name} {definition}"))
            order_rows = await connection.execute(text("pragma table_info(orders)"))
            order_columns = {row[1] for row in order_rows}
            if "budget_amount" not in order_columns:
                await connection.execute(text("alter table orders add column budget_amount integer not null default 0"))
            payment_rows = await connection.execute(text("pragma table_info(payments)"))
            payment_columns = {row[1] for row in payment_rows}
            if "service_fee" not in payment_columns:
                await connection.execute(text("alter table payments add column service_fee integer not null default 0"))
            if "worker_amount" not in payment_columns:
                await connection.execute(text("alter table payments add column worker_amount integer not null default 0"))
        elif dialect == "postgresql":
            await connection.execute(text("alter table users add column if not exists avatar_url text"))
            await connection.execute(text("alter table users alter column avatar_url type text"))
            await connection.execute(
                text("alter table users add column if not exists identity_status varchar(32) not null default 'not_verified'")
            )
            await connection.execute(text("alter table users add column if not exists passport_full_name varchar(160)"))
            await connection.execute(text("alter table users add column if not exists passport_number varchar(32)"))
            await connection.execute(text("alter table orders add column if not exists budget_amount integer not null default 0"))
            await connection.execute(text("alter type order_status add value if not exists 'disputed'"))
            await connection.execute(text("alter table payments add column if not exists service_fee integer not null default 0"))
            await connection.execute(text("alter table payments add column if not exists worker_amount integer not null default 0"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.create_tables_on_startup:
        from app import models  # noqa: F401

        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await ensure_local_schema_columns()

    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)
