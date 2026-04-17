# TaskNow

TaskNow - веб-приложение для подбора исполнителей на срочные бытовые и рабочие задачи. Заказчик создает задачу, система назначает свободного работника, исполнитель принимает заказ, ведет переписку, выполняет работу, а заказчик подтверждает результат и оставляет оценку.

Проект собран как MVP маркетплейса услуг с личными кабинетами, авторизацией, заказами, чатом, внутренними платежами и админкой для споров.

## Возможности

### Заказчик

- регистрация и вход по email/паролю;
- создание задачи с описанием, адресом, временем и бюджетом;
- просмотр активных и завершенных заказов;
- просмотр назначенного исполнителя, аватара и рейтинга;
- чат с исполнителем после принятия заказа;
- подтверждение завершения работы;
- оценка и отзыв после выполнения;
- открытие спора по активному заказу;
- просмотр платежей, резервов и истории операций;
- редактирование профиля, телефона, email, пароля и аватара.

### Работник

- регистрация с выбором навыков;
- статус смены: `На смене` / `Не на смене`;
- автоматическое получение задачи после выхода на смену;
- принятие, старт и отправка заказа на подтверждение;
- чат с заказчиком;
- просмотр рейтинга и отзывов;
- платежный кабинет с балансом, резервом и имитацией вывода средств;
- редактирование профиля, пароля, аватара и mock-подтверждение личности.

### Администратор

- вход через встроенный admin-аккаунт;
- список открытых споров;
- просмотр заказа, платежа и чата спора;
- решение спора: выплата исполнителю или возврат заказчику;
- системное сообщение в чат спора после решения.

### Система

- JWT-авторизация;
- автоматическое назначение доступного работника;
- уведомления;
- чат по заказу;
- внутренняя платежная модель без реального эквайринга;
- комиссия сервиса 10% при выплате исполнителю;
- возврат заказчику без комиссии;
- автообновление кабинета без ручного обновления страницы;
- сохранение текущего экрана после обновления страницы;
- загрузка и кадрирование аватара.

## Стек

| Часть | Технологии |
| --- | --- |
| Backend | Python, FastAPI, SQLAlchemy async, Pydantic |
| Frontend | Svelte, Vite, TypeScript |
| База данных | SQLite для локальной разработки, PostgreSQL для сервера |
| Auth | JWT Bearer token |
| Production | Linux VPS, Docker Compose, PostgreSQL, Nginx |

## Структура проекта

```text
TaskNow/
  backend/
    app/
      api/routes/       API routes
      core/             настройки и безопасность
      db/               подключение к базе
      models/           SQLAlchemy-модели
      schemas/          Pydantic-схемы
      services/         бизнес-логика
    tests/              backend-тесты
    requirements.txt
    .env.example

  frontend/
    src/
      lib/              API-клиент и типы
      App.svelte        основной интерфейс
      styles.css
    package.json
    .env.example

  infra/postgres/init/  SQL init для PostgreSQL
  docker-compose.yml    PostgreSQL для локального Docker-сценария
```

## Локальный запуск

Локально проект проще запускать на SQLite. Docker Desktop на текущей Windows-машине не обязателен.

### Backend

```powershell
cd C:\Users\User\PycharmProjects\TaskNow\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Backend:

```text
http://localhost:8000
```

Swagger:

```text
http://localhost:8000/docs
```

Health-check:

```text
http://localhost:8000/api/v1/health
```

### Frontend

```powershell
cd C:\Users\User\PycharmProjects\TaskNow\frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Frontend:

```text
http://localhost:5173
```

## Переменные окружения

### Backend `.env`

```env
DATABASE_URL=sqlite+aiosqlite:///./tasknow.db
CORS_ORIGINS=["http://localhost:5173"]
CREATE_TABLES_ON_STARTUP=true
SECRET_KEY=change-this-secret-key-before-production
ACCESS_TOKEN_EXPIRE_MINUTES=1440
JWT_ALGORITHM=HS256
```

Для PostgreSQL:

```env
DATABASE_URL=postgresql+asyncpg://tasknow:password@postgres:5432/tasknow
```

### Frontend `.env`

```env
VITE_API_URL=http://localhost:8000
```

Важно: `VITE_API_URL` указывается без `/api/v1`. Frontend добавляет `/api/v1` сам.

## Основные API

### Auth

- `POST /api/v1/auth/register` - регистрация.
- `POST /api/v1/auth/login` - вход.
- `POST /api/v1/auth/token` - OAuth2 form-login для Swagger.
- `GET /api/v1/auth/me` - текущий профиль.
- `PUT /api/v1/auth/me/profile` - обновление профиля.
- `PUT /api/v1/auth/me/password` - смена пароля.
- `PUT /api/v1/auth/me/avatar` - обновление аватара.
- `POST /api/v1/auth/me/identity` - mock-подтверждение личности.

### Workers

- `GET /api/v1/workers` - список работников.
- `GET /api/v1/workers/me` - профиль текущего работника.
- `POST /api/v1/workers/me/availability` - выход на смену или завершение смены.
- `GET /api/v1/workers/me/reviews` - отзывы текущего работника.

### Orders

- `POST /api/v1/orders/me` - создать заказ от текущего заказчика.
- `GET /api/v1/orders/me` - список заказов текущего пользователя.
- `GET /api/v1/orders/me/{order_id}` - один свой заказ.
- `POST /api/v1/orders/{order_id}/accept/me` - принять заказ.
- `POST /api/v1/orders/{order_id}/decline/me` - отклонить заказ.
- `POST /api/v1/orders/{order_id}/start/me` - начать работу.
- `POST /api/v1/orders/{order_id}/complete/me` - отправить на подтверждение.
- `POST /api/v1/orders/{order_id}/confirm-complete/me` - подтвердить выполнение.
- `POST /api/v1/orders/{order_id}/review/me` - оставить отзыв.
- `POST /api/v1/orders/{order_id}/dispute/me` - открыть спор.

### Messages

- `GET /api/v1/orders/{order_id}/messages` - сообщения по заказу.
- `POST /api/v1/orders/{order_id}/messages` - отправить сообщение.
- `GET /api/v1/messages/unread-count` - счетчик непрочитанных сообщений.

### Payments

- `GET /api/v1/payments/me` - платежный кабинет.
- `POST /api/v1/payments/me/payout` - имитация вывода средств работником.

### Notifications

- `GET /api/v1/notifications/me` - уведомления текущего пользователя.
- `POST /api/v1/notifications/{notification_id}/read/me` - отметить уведомление прочитанным.

### Admin

- `GET /api/v1/admin/disputes` - список открытых споров.
- `GET /api/v1/admin/disputes/{order_id}` - детали спора.
- `POST /api/v1/admin/disputes/{order_id}/resolve` - решение спора.

## Роли и демо-вход

Пользователи создаются через регистрацию в интерфейсе.

Администратор:

```text
login: admin
password: admin
```

Для публичного сервера пароль администратора нужно менять в коде или выносить в переменные окружения перед реальным использованием.

## Проверки

Backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m compileall app
pytest -p no:cacheprovider
```

Frontend:

```powershell
cd frontend
npm run build
```

Health-check:

```powershell
curl http://localhost:8000/api/v1/health
```

Ожидаемый ответ:

```json
{"status":"ok"}
```

## Серверный деплой

На сервере проект запускается через Docker Compose: PostgreSQL, backend, frontend и Nginx reverse proxy.

Обычное обновление сервера:

```bash
cd /opt/tasknow
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Проверка контейнеров:

```bash
docker compose -f docker-compose.prod.yml ps
```

Проверка backend:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Проверка API через Nginx:

```bash
curl http://127.0.0.1/api/v1/health
```

Логи backend:

```bash
docker compose -f docker-compose.prod.yml logs --tail=80 backend
```

## Обновление проекта

На компьютере:

```powershell
cd C:\Users\User\PycharmProjects\TaskNow
git add .
git commit -m "Update project"
git push
```

На сервере:

```bash
cd /opt/tasknow
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

После обновления frontend в браузере желательно сделать жесткое обновление:

```text
Ctrl + F5
```

## Важные замечания

- Настоящие `.env` файлы не должны попадать в Git.
- SQLite подходит для локальной разработки.
- PostgreSQL используется на сервере.
- `CREATE_TABLES_ON_STARTUP=true` включает автоматическое создание таблиц и легкие startup-миграции.
- Аватары хранятся как `data URL` в поле `avatar_url`.
- Внутренние платежи являются имитацией и не подключены к реальному эквайрингу.
