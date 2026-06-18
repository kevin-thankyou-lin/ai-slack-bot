from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from slack_bolt.async_app import AsyncApp

from claude_slack_bot.core.coordinator import ThreadCoordinator
from claude_slack_bot.db import queries
from claude_slack_bot.db.database import Database
from claude_slack_bot.slack.assistant import (
    ASSISTANT_SURFACE,
    AssistantSay,
    _assistant_text_from_payload,
    _is_known_assistant_thread,
    register_assistant,
)


class _FakeBackend:
    default_backend_type = "codex"

    def __init__(self) -> None:
        self.created = 0
        self.registered: list[tuple[str, str]] = []

    def available_backend_types(self) -> tuple[str, ...]:
        return ("codex",)

    async def create_session(self, system_prompt: str | None = None, backend_type: str | None = None) -> str:
        self.created += 1
        return f"sess-{self.created}"

    def register_session(self, session_id: str, backend_type: str) -> None:
        self.registered.append((session_id, backend_type))


def test_register_assistant_accepts_custom_matcher() -> None:
    app = AsyncApp(token="xoxb-test")

    register_assistant(app, object())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_assistant_say_delegates_and_exposes_utilities() -> None:
    say = AsyncMock(return_value={"ts": "1.2", "channel": "D1"})
    set_status = AsyncMock()
    set_title = AsyncMock()
    wrapped = AssistantSay(say, set_status=set_status, set_title=set_title)

    result = await wrapped(text="hello", thread_ts="1.2")
    await wrapped.set_status("is working")
    await wrapped.set_title("Task title")

    assert result == {"ts": "1.2", "channel": "D1"}
    say.assert_awaited_once_with(text="hello", thread_ts="1.2")
    set_status.assert_awaited_once_with("is working")
    set_title.assert_awaited_once_with("Task title")


@pytest.mark.asyncio
async def test_mark_assistant_thread_persists_surface(db: Database) -> None:
    backend = _FakeBackend()
    coordinator = ThreadCoordinator(backend=backend, db=db)

    thread = await coordinator.mark_assistant_thread("1729999327.187299", "D123", user_id="U123")

    assert thread.surface == ASSISTANT_SURFACE
    assert thread.session_id == "sess-1"
    async with db._connect() as conn:
        stored = await queries.get_thread(conn, "1729999327.187299")
    assert stored is not None
    assert stored.surface == ASSISTANT_SURFACE
    assert stored.channel_id == "D123"
    assert stored.user_id == "U123"


@pytest.mark.asyncio
async def test_assistant_matcher_only_allows_persisted_assistant_threads(db: Database) -> None:
    coordinator = ThreadCoordinator(backend=_FakeBackend(), db=db)
    payload = {"thread_ts": "1729999327.187299"}

    assert await _is_known_assistant_thread(payload, coordinator) is False

    await coordinator.mark_assistant_thread("1729999327.187299", "D123", user_id="U123")

    assert await _is_known_assistant_thread(payload, coordinator) is True


@pytest.mark.asyncio
async def test_assistant_text_from_payload_strips_mentions_and_keeps_text() -> None:
    client: Any = object()

    text = await _assistant_text_from_payload({"text": "<@U999>  please inspect this"}, client)

    assert text == "please inspect this"
