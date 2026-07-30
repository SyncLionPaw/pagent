-- Cloud backend initial schema
-- Stage 1: jwt auth + per-user thread storage
-- Target: PostgreSQL 15+

create extension if not exists pgcrypto;


create table users (
    id uuid primary key default gen_random_uuid(),
    email text not null,
    display_name text,
    avatar_url text,
    status text not null default 'active' check (status in ('pending', 'active', 'disabled', 'deleted')),
    email_verified_at timestamptz,
    last_login_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (email)
);


create table user_passwords (
    user_id uuid primary key references users(id) on delete cascade,
    password_hash text not null,
    password_algo text not null default 'argon2id',
    password_updated_at timestamptz not null default now(),
    must_reset boolean not null default false,
    created_at timestamptz not null default now()
);


create table threads (
    id uuid primary key default gen_random_uuid(),
    owner_user_id uuid not null references users(id) on delete cascade,
    title text not null default '',
    status text not null default 'idle' check (status in ('idle', 'running', 'completed', 'error', 'archived')),
    sandbox_backend text,
    model text,
    project_path text,
    summary text,
    message_count integer not null default 0 check (message_count >= 0),
    started_at timestamptz,
    last_message_at timestamptz,
    archived_at timestamptz,
    deleted_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index threads_owner_user_id_last_message_at_idx
    on threads (owner_user_id, last_message_at desc nulls last, created_at desc);

create index threads_owner_user_id_deleted_at_idx
    on threads (owner_user_id, deleted_at);


create table thread_messages (
    id uuid primary key default gen_random_uuid(),
    thread_id uuid not null references threads(id) on delete cascade,
    owner_user_id uuid not null references users(id) on delete cascade,
    seq integer not null check (seq >= 1),
    role text not null check (role in ('system', 'user', 'assistant', 'tool')),
    turn_id integer,
    tool_call_id text,
    content_text text,
    content_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (thread_id, seq)
);

create index thread_messages_thread_id_seq_idx
    on thread_messages (thread_id, seq);

create index thread_messages_owner_user_id_created_at_idx
    on thread_messages (owner_user_id, created_at desc);


create table thread_artifacts (
    id uuid primary key default gen_random_uuid(),
    thread_id uuid not null references threads(id) on delete cascade,
    owner_user_id uuid not null references users(id) on delete cascade,
    message_id uuid references thread_messages(id) on delete set null,
    name text not null,
    storage_key text not null unique,
    content_type text,
    size_bytes bigint not null default 0 check (size_bytes >= 0),
    sha256 text,
    created_at timestamptz not null default now()
);

create index thread_artifacts_thread_id_created_at_idx
    on thread_artifacts (thread_id, created_at desc);

create index thread_artifacts_owner_user_id_created_at_idx
    on thread_artifacts (owner_user_id, created_at desc);
