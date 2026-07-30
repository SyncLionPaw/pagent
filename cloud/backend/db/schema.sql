-- Cloud backend initial schema
-- Target: PostgreSQL 15+
-- Notes:
-- 1. This is the initial schema for the cloud version only.
-- 2. updated_at is maintained by the application layer for now.

create extension if not exists pgcrypto;


create table users (
    id uuid primary key default gen_random_uuid(),
    email text,
    username text not null,
    display_name text,
    avatar_url text,
    status text not null default 'active' check (status in ('pending', 'active', 'disabled', 'deleted')),
    email_verified_at timestamptz,
    last_login_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (email),
    unique (username)
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


create table personal_access_tokens (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    name text not null,
    token_hash text not null unique,
    last_used_at timestamptz,
    expires_at timestamptz,
    revoked_at timestamptz,
    created_at timestamptz not null default now()
);

create index personal_access_tokens_user_id_idx on personal_access_tokens (user_id);


create table workspaces (
    id uuid primary key default gen_random_uuid(),
    owner_user_id uuid not null references users(id),
    name text not null,
    slug text not null unique,
    visibility text not null default 'private' check (visibility in ('private', 'internal')),
    status text not null default 'active' check (status in ('active', 'archived')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index workspaces_owner_user_id_idx on workspaces (owner_user_id);


create table workspace_members (
    workspace_id uuid not null references workspaces(id) on delete cascade,
    user_id uuid not null references users(id) on delete cascade,
    role text not null check (role in ('owner', 'admin', 'member', 'viewer')),
    invited_by_user_id uuid references users(id),
    joined_at timestamptz not null default now(),
    primary key (workspace_id, user_id)
);

create index workspace_members_user_id_idx on workspace_members (user_id);


create table projects (
    id uuid primary key default gen_random_uuid(),
    workspace_id uuid not null references workspaces(id) on delete cascade,
    created_by_user_id uuid not null references users(id),
    name text not null,
    slug text not null,
    git_url text,
    default_branch text,
    runtime_config jsonb not null default '{}'::jsonb,
    status text not null default 'active' check (status in ('active', 'archived')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (workspace_id, slug)
);

create index projects_workspace_id_idx on projects (workspace_id);
create index projects_created_by_user_id_idx on projects (created_by_user_id);


create table threads (
    id uuid primary key default gen_random_uuid(),
    project_id uuid not null references projects(id) on delete cascade,
    created_by_user_id uuid not null references users(id),
    title text not null default '',
    status text not null default 'idle' check (status in ('idle', 'running', 'completed', 'error', 'archived')),
    sandbox_backend text,
    model text,
    started_at timestamptz,
    finished_at timestamptz,
    last_message_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index threads_project_id_idx on threads (project_id);
create index threads_created_by_user_id_idx on threads (created_by_user_id);
create index threads_last_message_at_idx on threads (last_message_at desc);


create table messages (
    id uuid primary key default gen_random_uuid(),
    thread_id uuid not null references threads(id) on delete cascade,
    seq integer not null,
    role text not null check (role in ('system', 'user', 'assistant', 'tool')),
    sender_user_id uuid references users(id),
    tool_call_id text,
    content_text text,
    content_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (thread_id, seq)
);

create index messages_thread_id_created_at_idx on messages (thread_id, created_at);
create index messages_sender_user_id_idx on messages (sender_user_id);


create table artifacts (
    id uuid primary key default gen_random_uuid(),
    project_id uuid not null references projects(id) on delete cascade,
    thread_id uuid references threads(id) on delete cascade,
    created_by_user_id uuid references users(id),
    name text not null,
    storage_key text not null unique,
    content_type text,
    size_bytes bigint not null default 0 check (size_bytes >= 0),
    sha256 text,
    source text not null default 'agent' check (source in ('agent', 'user', 'system')),
    created_at timestamptz not null default now()
);

create index artifacts_project_id_idx on artifacts (project_id);
create index artifacts_thread_id_idx on artifacts (thread_id);
create index artifacts_created_by_user_id_idx on artifacts (created_by_user_id);
