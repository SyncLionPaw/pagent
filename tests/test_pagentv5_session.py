from pathlib import Path

import pytest

from pagentv5.session import (
    JsonlSessionBackend,
    MemorySessionBackend,
    Session,
    SessionBackend,
    SessionConfig,
    SqliteSessionBackend,
    validate_session_id,
)


def make_backends(tmp_path: Path):
    return [
        MemorySessionBackend(),
        JsonlSessionBackend(tmp_path / "jsonl"),
        SqliteSessionBackend(tmp_path / "sessions.sqlite"),
    ]


def close_backends(backends) -> None:
    for backend in backends:
        backend.close()


def test_session_id_validation():
    validate_session_id("task-1.messages")
    with pytest.raises(ValueError, match="invalid session_id"):
        validate_session_id("../escape")


def test_all_session_backends_follow_protocol(tmp_path: Path):
    backends = make_backends(tmp_path)
    try:
        assert all(isinstance(backend, SessionBackend) for backend in backends)
    finally:
        close_backends(backends)


def test_all_backends_save_load_list_and_delete(tmp_path: Path):
    backends = make_backends(tmp_path)
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    try:
        for backend in backends:
            backend.save("one", messages)
            assert backend.load("one") == messages
            assert backend.list() == ["one"]

            loaded = backend.load("one")
            loaded[0]["content"] = "mutated"
            assert backend.load("one")[0]["content"] == "hello"

            backend.delete("one")
            assert backend.load("one") == []
            assert backend.list() == []
    finally:
        close_backends(backends)


def test_jsonl_backend_writes_one_message_per_line(tmp_path: Path):
    backend = JsonlSessionBackend(tmp_path)
    backend.save(
        "messages",
        [
            {"role": "user", "content": "一"},
            {"role": "assistant", "content": "二"},
        ],
    )

    lines = backend.path_for("messages").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert '"role": "user"' in lines[0]


def test_session_handle_persists_mutations(tmp_path: Path):
    config = SessionConfig(
        storage="jsonl",
        session_id="messages",
        root="messages",
    )
    session = Session.open(config, base_path=tmp_path)
    session.append({"role": "user", "content": "hello"})
    session.extend([{"role": "assistant", "content": "hi"}])
    session.close()

    reopened = Session.open(config, base_path=tmp_path)
    assert reopened.messages == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    reopened.clear()
    assert reopened.messages == []
    reopened.delete()
    reopened.close()


def test_session_rejects_use_after_close():
    session = Session("messages", MemorySessionBackend())
    session.close()

    with pytest.raises(RuntimeError, match="closed"):
        session.append({"role": "user", "content": "hello"})


def test_session_messages_must_be_json_objects(tmp_path: Path):
    backend = JsonlSessionBackend(tmp_path)
    with pytest.raises(TypeError, match="must be an object"):
        backend.save("messages", ["invalid"])
    with pytest.raises(TypeError):
        backend.save("messages", [{"content": object()}])
