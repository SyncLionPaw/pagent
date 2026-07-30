-- Cloud backend initial schema
-- Stage 1: auth only
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


create table user_oauth_accounts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    provider text not null,
    provider_user_id text not null,
    provider_email text,
    profile jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (provider, provider_user_id)
);

create index user_oauth_accounts_user_id_idx on user_oauth_accounts (user_id);


create table user_sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    session_token_hash text not null unique,
    refresh_token_hash text unique,
    ip inet,
    user_agent text,
    expires_at timestamptz not null,
    revoked_at timestamptz,
    last_seen_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create index user_sessions_user_id_idx on user_sessions (user_id);
create index user_sessions_expires_at_idx on user_sessions (expires_at);
