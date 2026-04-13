# TaskNow

TaskNow - MVP для автоматизации подбора разнорабочих: заказчик создает задачу, система назначает свободного исполнителя, работник принимает и выполняет заказ, заказчик ставит оценку.

## Что уже заложено

- Backend: FastAPI, SQLAlchemy async, SQLite для локального dev-режима без Docker; PostgreSQL поддерживается через `DATABASE_URL`.
- Frontend: Svelte + Vite, один рабочий экран для сценариев заказчика и работника.
- База: пользователи, профили работников, заказы, уведомления, отзывы и рейтинг.
- Автоподбор: выбирается доступный активный работник с лучшим рейтингом и без активного заказа.

## Структура

```text
backend/                FastAPI-приложение
frontend/               Svelte-приложение
infra/postgres/init/    SQL-инициализация PostgreSQL
docker-compose.yml      Опциональный PostgreSQL для локальной разработки
```

## Запуск локально

На этой машине Docker Desktop использовать нельзя из-за отсутствующей virtualization/WSL, поэтому основной dev-запуск идет через SQLite-файл `backend/tasknow.db`.

1. Запустить backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Backend будет доступен на `http://localhost:8000`, Swagger - на `http://localhost:8000/docs`.

2. Запустить frontend:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Frontend будет доступен на `http://localhost:5173`.

Если позже появится рабочий Docker/WSL или отдельный PostgreSQL, можно переключить backend обратно на PostgreSQL:

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://tasknow:tasknow@localhost:5433/tasknow"
```

PostgreSQL из Docker Compose публикуется на `localhost:5433`, чтобы не конфликтовать с локальной установкой PostgreSQL на `5432`.

## Основные API

- `POST /api/v1/customers` - создать заказчика.
- `POST /api/v1/workers` - создать работника.
- `POST /api/v1/auth/register` - создать аккаунт с паролем и получить JWT.
- `POST /api/v1/auth/login` - войти по email и паролю.
- `POST /api/v1/auth/token` - form-data логин для Swagger OAuth2 Authorize.
- `GET /api/v1/auth/me` - получить текущий профиль по Bearer token.
- `GET /api/v1/workers/me` - получить профиль текущего работника.
- `POST /api/v1/workers/me/availability?availability=available` - сменить доступность текущего работника.
- `POST /api/v1/orders` - создать заказ и запустить автоподбор.
- `POST /api/v1/orders/me` - создать заказ от текущего заказчика по Bearer token.
- `GET /api/v1/orders/me` - получить заказы текущего заказчика или работника.
- `GET /api/v1/orders/me/{order_id}` - получить свой заказ.
- `POST /api/v1/orders/{order_id}/accept` - принять заказ.
- `POST /api/v1/orders/{order_id}/accept/me` - принять назначенный заказ от текущего работника.
- `POST /api/v1/orders/{order_id}/decline` - отклонить и попробовать переназначить.
- `POST /api/v1/orders/{order_id}/decline/me` - отклонить назначенный заказ от текущего работника.
- `POST /api/v1/orders/{order_id}/start` - начать выполнение.
- `POST /api/v1/orders/{order_id}/start/me` - начать выполнение от текущего работника.
- `POST /api/v1/orders/{order_id}/complete` - завершить заказ.
- `POST /api/v1/orders/{order_id}/complete/me` - завершить заказ от текущего работника.
- `POST /api/v1/orders/{order_id}/review` - поставить оценку.
- `POST /api/v1/orders/{order_id}/review/me` - поставить оценку от текущего заказчика.
- `GET /api/v1/notifications?user_id=...` - получить уведомления пользователя.
- `GET /api/v1/notifications/me` - получить свои уведомления по Bearer token.
- `POST /api/v1/notifications/{notification_id}/read/me` - отметить свое уведомление прочитанным.

На этапе MVP старые order endpoints еще принимают `customer_id` и `worker_id` явно для быстрой ручной проверки. Frontend уже использует auth и `/me` endpoints; следующий логичный слой - проверить сценарий на запущенном backend и затем закрыть старые публичные бизнес endpoints.
