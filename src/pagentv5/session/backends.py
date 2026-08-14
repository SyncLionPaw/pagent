from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from copy import deepcopy
from pathlib import Path
from urllib.parse import quote, unquote

from .protocol import SessionMessage

SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,127}$")


def validate_session_id(session_id: str) -> None:
    if SESSION_ID_PATTERN.fullmatch(session_id):
        return
    raise ValueError(
        f"invalid session_id: {session_id!r}; "
        "must match [A-Za-z0-9][A-Za-z0-9_.-]{0,127}"
    )


def normalize_messages(messages: list[SessionMessage]) -> list[SessionMessage]:
    normalized: list[SessionMessage] = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise TypeError(f"session message {index} must be an object")
        json.dumps(message, ensure_ascii=False)
        normalized.append(deepcopy(message))
    return normalized


class MemorySessionBackend:
    def __init__(self) -> None:
        self.sessions: dict[str, list[SessionMessage]] = {}
        self.updated_at: dict[str, int] = {}

    def save(self, session_id: str, messages: list[SessionMessage]) -> None:
        validate_session_id(session_id)
        self.sessions[session_id] = normalize_messages(messages)
        self.updated_at[session_id] = time.time_ns()

    def load(self, session_id: str) -> list[SessionMessage]:
        validate_session_id(session_id)
        return deepcopy(self.sessions.get(session_id, []))

    def list(self) -> list[str]:
        return sorted(
            self.sessions,
            key=lambda session_id: (-self.updated_at[session_id], session_id),
        )

    def delete(self, session_id: str) -> None:
        validate_session_id(session_id)
        self.sessions.pop(session_id, None)
        self.updated_at.pop(session_id, None)

    def close(self) -> None:
        return


class JsonlSessionBackend:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, session_id: str) -> Path:
        validate_session_id(session_id)
        return self.root / f"{quote(session_id, safe='')}.jsonl"

    def save(self, session_id: str, messages: list[SessionMessage]) -> None:
        path = self.path_for(session_id)
        normalized = normalize_messages(messages)
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        with temporary.open("w", encoding="utf-8") as file:
            for message in normalized:
                file.write(json.dumps(message, ensure_ascii=False) + "\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)

    def load(self, session_id: str) -> list[SessionMessage]:
        path = self.path_for(session_id)
        if not path.exists():
            return []
        messages: list[SessionMessage] = []
        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                raw = line.strip()
                if not raw:
                    continue
                message = json.loads(raw)
                if not isinstance(message, dict):
                    raise ValueError(
                        f"{path}:{line_number}: session message must be an object"
                    )
                messages.append(message)
        return messages

    def list(self) -> list[str]:
        paths = sorted(
            self.root.glob("*.jsonl"),
            key=lambda path: (-path.stat().st_mtime_ns, path.name),
        )
        return [unquote(path.stem) for path in paths]

    def delete(self, session_id: str) -> None:
        path = self.path_for(session_id)
        if path.exists():
            path.unlink()

    def close(self) -> None:
        return


class SqliteSessionBackend:
    def __init__(self, database: str | Path) -> None:
        self.database = Path(database).expanduser().resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database)
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                messages_json TEXT NOT NULL,
                updated_at_ns INTEGER NOT NULL
            )
            """
        )
        self.connection.commit()
        self.closed = False

    def save(self, session_id: str, messages: list[SessionMessage]) -> None:
        validate_session_id(session_id)
        payload = json.dumps(normalize_messages(messages), ensure_ascii=False)
        self.connection.execute(
            """
            INSERT INTO sessions (session_id, messages_json, updated_at_ns)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                messages_json = excluded.messages_json,
                updated_at_ns = excluded.updated_at_ns
            """,
            (session_id, payload, time.time_ns()),
        )
        self.connection.commit()

    def load(self, session_id: str) -> list[SessionMessage]:
        validate_session_id(session_id)
        row = self.connection.execute(
            "SELECT messages_json FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return []
        messages = json.loads(row[0])
        if not isinstance(messages, list):
            raise ValueError(f"session {session_id!r} payload must be a list")
        return normalize_messages(messages)

    def list(self) -> list[str]:
        rows = self.connection.execute(
            """
            SELECT session_id FROM sessions
            ORDER BY updated_at_ns DESC, session_id ASC
            """
        ).fetchall()
        return [row[0] for row in rows]

    def delete(self, session_id: str) -> None:
        validate_session_id(session_id)
        self.connection.execute(
            "DELETE FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        self.connection.commit()

    def close(self) -> None:
        if self.closed:
            return
        self.connection.close()
        self.closed = True
