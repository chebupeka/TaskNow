create extension if not exists pgcrypto;

do $$
begin
    create type user_role as enum ('customer', 'worker', 'admin');
exception
    when duplicate_object then null;
end $$;

do $$
begin
    create type worker_availability as enum ('available', 'busy', 'offline');
exception
    when duplicate_object then null;
end $$;

do $$
begin
    create type order_status as enum ('pending', 'assigned', 'accepted', 'in_progress', 'completion_requested', 'completed', 'reviewed', 'disputed', 'canceled');
exception
    when duplicate_object then null;
end $$;

alter type order_status add value if not exists 'completion_requested';
alter type order_status add value if not exists 'disputed';

do $$
begin
    create type notification_kind as enum (
        'order_pending',
        'order_assigned',
        'order_reassigned',
        'order_accepted',
        'order_declined',
        'order_completion_requested',
        'order_completed',
        'order_ready_to_review',
        'review_received'
    );
exception
    when duplicate_object then null;
end $$;

alter type notification_kind add value if not exists 'order_completion_requested';
alter type notification_kind add value if not exists 'order_completed';

do $$
begin
    create type payment_status as enum ('pending', 'held', 'released', 'refunded', 'disputed');
exception
    when duplicate_object then null;
end $$;

do $$
begin
    create type payout_status as enum ('paid');
exception
    when duplicate_object then null;
end $$;

create table if not exists users (
    id uuid primary key default gen_random_uuid(),
    role user_role not null,
    full_name varchar(160) not null,
    phone varchar(32) unique,
    email varchar(255) unique,
    hashed_password varchar(255),
    avatar_url text,
    identity_status varchar(32) not null default 'not_verified',
    passport_full_name varchar(160),
    passport_number varchar(32),
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

alter table users add column if not exists hashed_password varchar(255);
alter table users add column if not exists avatar_url text;
alter table users alter column avatar_url type text;
alter table users add column if not exists identity_status varchar(32) not null default 'not_verified';
alter table users add column if not exists passport_full_name varchar(160);
alter table users add column if not exists passport_number varchar(32);

create index if not exists ix_users_role on users (role);
create index if not exists ix_users_phone on users (phone);
create index if not exists ix_users_email on users (email);

create table if not exists worker_profiles (
    user_id uuid primary key references users(id) on delete cascade,
    skills jsonb not null default '[]'::jsonb,
    availability worker_availability not null default 'available',
    rating_avg double precision not null default 0,
    rating_count integer not null default 0,
    completed_orders integer not null default 0,
    city varchar(120),
    current_lat double precision,
    current_lng double precision,
    updated_at timestamptz not null default now()
);

create index if not exists ix_worker_profiles_availability on worker_profiles (availability);
create index if not exists ix_worker_profiles_city on worker_profiles (city);
alter table worker_profiles add column if not exists city varchar(120);

create table if not exists orders (
    id uuid primary key default gen_random_uuid(),
    customer_id uuid not null references users(id) on delete restrict,
    worker_id uuid references users(id) on delete set null,
    description text not null,
    budget_amount integer not null default 0,
    city varchar(120),
    address varchar(500) not null,
    scheduled_at timestamptz not null,
    status order_status not null default 'pending',
    assigned_at timestamptz,
    decision_at timestamptz,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists ix_orders_customer_id on orders (customer_id);
create index if not exists ix_orders_worker_id on orders (worker_id);
create index if not exists ix_orders_scheduled_at on orders (scheduled_at);
create index if not exists ix_orders_status on orders (status);
create index if not exists ix_orders_city on orders (city);
create index if not exists ix_orders_status_scheduled_at on orders (status, scheduled_at);

alter table orders add column if not exists budget_amount integer not null default 0;
alter table orders add column if not exists city varchar(120);

create table if not exists chat_messages (
    id uuid primary key default gen_random_uuid(),
    order_id uuid not null references orders(id) on delete cascade,
    sender_id uuid not null references users(id) on delete cascade,
    body text not null,
    sent_at timestamptz not null default now(),
    read_at timestamptz,
    client_message_id varchar(64)
);

create index if not exists ix_chat_messages_order_id on chat_messages (order_id);
create index if not exists ix_chat_messages_sender_id on chat_messages (sender_id);
create index if not exists ix_chat_messages_client_message_id on chat_messages (client_message_id);

create table if not exists payments (
    id uuid primary key default gen_random_uuid(),
    order_id uuid not null unique references orders(id) on delete cascade,
    customer_id uuid not null references users(id) on delete cascade,
    worker_id uuid references users(id) on delete set null,
    amount integer not null,
    service_fee integer not null default 0,
    worker_amount integer not null default 0,
    status payment_status not null default 'pending',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists ix_payments_order_id on payments (order_id);
create index if not exists ix_payments_customer_id on payments (customer_id);
create index if not exists ix_payments_worker_id on payments (worker_id);
create index if not exists ix_payments_status on payments (status);

alter table payments add column if not exists service_fee integer not null default 0;
alter table payments add column if not exists worker_amount integer not null default 0;

create table if not exists wallets (
    user_id uuid primary key references users(id) on delete cascade,
    balance_available integer not null default 0,
    balance_paid_out integer not null default 0,
    updated_at timestamptz not null default now()
);

create table if not exists payouts (
    id uuid primary key default gen_random_uuid(),
    worker_id uuid not null references users(id) on delete cascade,
    amount integer not null,
    status payout_status not null default 'paid',
    created_at timestamptz not null default now()
);

create index if not exists ix_payouts_worker_id on payouts (worker_id);

create table if not exists reviews (
    id uuid primary key default gen_random_uuid(),
    order_id uuid not null unique references orders(id) on delete cascade,
    customer_id uuid not null references users(id) on delete restrict,
    worker_id uuid not null references users(id) on delete restrict,
    score integer not null constraint ck_reviews_score_range check (score between 1 and 5),
    comment varchar(1000),
    created_at timestamptz not null default now()
);

create index if not exists ix_reviews_order_id on reviews (order_id);

create table if not exists notifications (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    order_id uuid references orders(id) on delete cascade,
    kind notification_kind not null,
    title varchar(160) not null,
    body varchar(500) not null,
    is_read boolean not null default false,
    created_at timestamptz not null default now()
);

create index if not exists ix_notifications_user_id on notifications (user_id);
create index if not exists ix_notifications_order_id on notifications (order_id);
create index if not exists ix_notifications_kind on notifications (kind);
