"""threads 登记表访问：谁拥有哪些会话，用于多用户隔离与会话列表。

对话消息内容由 conversation_store.PostgresConversationStore 写 thread_messages；这里只管
threads 表本身：创建、按 owner 列出、取单条、软删。隔离条件写死在每条 SQL 的
owner_user_id 过滤里，不接受调用方传 owner 之外的身份。

thread_id 用 uuid 字符串，同时作 pagentv4 的 thread_id 与 threads.id，一个 id 贯穿
引擎与数据库，无需映射。
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from . import db


def new_thread_id() -> str:
    return str(uuid4())


def create_thread(
    *,
    thread_id: str,
    owner_user_id: str,
    title: str = "",
    project_path: str | None = None,
    sandbox_backend: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into threads (
                    id, owner_user_id, title, status,
                    project_path, sandbox_backend, model
                ) values (
                    %s::uuid, %s::uuid, %s, 'idle', %s, %s, %s
                )
                returning id, title, status, project_path, sandbox_backend, model,
                          message_count, last_message_at, created_at, updated_at
                """,
                (
                    thread_id,
                    owner_user_id,
                    title,
                    project_path,
                    sandbox_backend,
                    model,
                ),
            )
            row = cur.fetchone()
            columns = [desc[0] for desc in cur.description]
        conn.commit()
    return row_to_thread(dict(zip(columns, row)))


def list_threads(owner_user_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, title, status, project_path, sandbox_backend, model,
                       message_count, last_message_at, created_at, updated_at
                  from threads
                 where owner_user_id = %s::uuid and deleted_at is null
                 order by last_message_at desc nulls last, created_at desc
                 limit %s
                """,
                (owner_user_id, limit),
            )
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
    return [row_to_thread(dict(zip(columns, row))) for row in rows]


def get_thread(thread_id: str, owner_user_id: str) -> dict[str, Any] | None:
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, title, status, project_path, sandbox_backend, model,
                       message_count, last_message_at, created_at, updated_at
                  from threads
                 where id = %s::uuid and owner_user_id = %s::uuid
                   and deleted_at is null
                """,
                (thread_id, owner_user_id),
            )
            row = cur.fetchone()
            columns = [desc[0] for desc in cur.description] if row else []
    if row is None:
        return None
    return row_to_thread(dict(zip(columns, row)))


def set_title_if_empty(thread_id: str, owner_user_id: str, title: str) -> None:
    """首条用户消息定标题：仅当当前标题为空时写入，之后不再覆盖。"""
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update threads
                   set title = %s, updated_at = now()
                 where id = %s::uuid and owner_user_id = %s::uuid
                   and (title is null or title = '')
                """,
                (title, thread_id, owner_user_id),
            )
        conn.commit()


def soft_delete(thread_id: str, owner_user_id: str) -> None:
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update threads
                   set deleted_at = now(), updated_at = now()
                 where id = %s::uuid and owner_user_id = %s::uuid
                """,
                (thread_id, owner_user_id),
            )
        conn.commit()


def row_to_thread(row: dict[str, Any]) -> dict[str, Any]:
    """把一行 threads 记录规整成前端消费的字段（id / title 供 ThreadList）。"""
    return {
        "id": str(row["id"]),
        "title": row["title"] or "",
        "status": row["status"],
        "project_path": row["project_path"] or "",
        "backend": row["sandbox_backend"] or "local",
        "model": row["model"] or "",
        "message_count": row["message_count"],
        "last_message_at": to_iso(row["last_message_at"]),
        "created_at": to_iso(row["created_at"]),
        "updated_at": to_iso(row["updated_at"]),
    }


def to_iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()
