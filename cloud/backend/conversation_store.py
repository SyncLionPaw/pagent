"""把 pagentv4 的对话消息直接落到 Postgres 的 thread_messages 表。

实现 pagentv4 的 ConversationStore 协议（save / load），注入进 Runner 后，引擎每次
checkpoint 就把消息写进数据库，不再产生磁盘 JSONL —— 换后端而非加副本，对话内容仍是
单一事实源。

一个 store 实例绑定一个 (thread_id, owner_user_id)：
- thread_id 同时是 pagentv4 的 thread_id 和 threads.id（uuid 字符串）。
- owner_user_id 在构造时锁定，隔离条件写死在数据层，不依赖调用方每次传对。

content_json 存整条 Message 的 dump（load 时据此完整还原，含 thinking / tool_call）；
role / seq / turn_id / tool_call_id / content_text 是从中摊平出来的列，供列表与查询。
"""

from __future__ import annotations

from psycopg.types.json import Json

from pagentv4.core.message import (
    Message,
    Messages,
    TextChunk,
    ThinkingChunk,
    ToolCall,
    ToolResult,
)

from . import db


def message_to_row(seq: int, message: Message) -> dict:
    """把一条 Message 摊平成 thread_messages 的一行字段。"""
    content = message.content
    tool_call_id = None
    content_text = None
    if isinstance(content, (TextChunk, ThinkingChunk)):
        content_text = content.text
    elif isinstance(content, ToolResult):
        content_text = content.text
        tool_call_id = content.tool_call_id
    elif isinstance(content, ToolCall):
        tool_call_id = content.id
    return {
        "seq": seq,
        "role": message.role,
        "turn_id": message.turn_id,
        "tool_call_id": tool_call_id,
        "content_text": content_text,
        "content_json": message.model_dump(mode="json"),
    }


INSERT_SQL = """
insert into thread_messages (
    thread_id, owner_user_id, seq, role, turn_id, tool_call_id, content_text, content_json
) values (
    %(thread_id)s::uuid, %(owner_user_id)s::uuid, %(seq)s, %(role)s,
    %(turn_id)s, %(tool_call_id)s, %(content_text)s, %(content_json)s
)
"""


class PostgresConversationStore:
    """thread_messages 版 ConversationStore；绑定单个 thread 与其 owner。"""

    def __init__(self, thread_id: str, owner_user_id: str):
        self.thread_id = thread_id
        self.owner_user_id = owner_user_id

    def save(self, conversation_id: str, messages: Messages) -> None:
        """整表重写本 thread 的消息，并回写 threads 计数。

        消息只增（末条可能因流式合并而变长），checkpoint 频率与消息量在演示规模下
        很小，先删后插最简单也最不易漂移；有需要再改增量 upsert。
        """
        del conversation_id
        rows = [
            message_to_row(seq, message)
            for seq, message in enumerate(messages.data, start=1)
        ]
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "delete from thread_messages where thread_id = %s::uuid",
                    (self.thread_id,),
                )
                for row in rows:
                    cur.execute(
                        INSERT_SQL,
                        {
                            "thread_id": self.thread_id,
                            "owner_user_id": self.owner_user_id,
                            "content_json": Json(row["content_json"]),
                            **{
                                key: row[key]
                                for key in (
                                    "seq",
                                    "role",
                                    "turn_id",
                                    "tool_call_id",
                                    "content_text",
                                )
                            },
                        },
                    )
                cur.execute(
                    """
                    update threads
                       set message_count = %s,
                           last_message_at = now(),
                           updated_at = now()
                     where id = %s::uuid and owner_user_id = %s::uuid
                    """,
                    (len(rows), self.thread_id, self.owner_user_id),
                )
            conn.commit()

    def load(self, conversation_id: str) -> Messages:
        """按 seq 顺序读回消息，用 content_json 完整还原每条 Message。"""
        del conversation_id
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select content_json
                      from thread_messages
                     where thread_id = %s::uuid
                     order by seq
                    """,
                    (self.thread_id,),
                )
                rows = cur.fetchall()
        messages = Messages()
        for (content_json,) in rows:
            messages.data.append(Message.model_validate(content_json))
        return messages

    def list(self) -> list[str]:
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select 1 from thread_messages where thread_id = %s::uuid limit 1",
                    (self.thread_id,),
                )
                found = cur.fetchone() is not None
        return [self.thread_id] if found else []

    def delete(self, conversation_id: str) -> None:
        del conversation_id
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "delete from thread_messages where thread_id = %s::uuid",
                    (self.thread_id,),
                )
            conn.commit()
