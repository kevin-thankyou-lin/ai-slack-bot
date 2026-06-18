from __future__ import annotations

import asyncio
from typing import AsyncIterator
from unittest.mock import AsyncMock

import pytest

import claude_slack_bot.core.coordinator as coordinator_module
from claude_slack_bot.agent.backend import EventType, SessionEvent
from claude_slack_bot.core.coordinator import ThreadCoordinator
from claude_slack_bot.db import queries
from claude_slack_bot.db.database import Database
from claude_slack_bot.db.models import Thread


class _DeltaBackend:
    async def create_session(self) -> str:
        return "sess-quiet"

    async def send_message(self, session_id: str, content: str) -> AsyncIterator[SessionEvent]:
        yield SessionEvent(type=EventType.TEXT_DELTA, text="hello")
        yield SessionEvent(type=EventType.TEXT_DELTA, text=" world")
        yield SessionEvent(type=EventType.TURN_END, is_final=True)


class _ConfirmationBackend(_DeltaBackend):
    async def send_tool_confirmation(
        self, session_id: str, tool_use_id: str, allowed: bool
    ) -> AsyncIterator[SessionEvent]:
        yield SessionEvent(type=EventType.TEXT_DELTA, text="denied")
        yield SessionEvent(type=EventType.TEXT_DELTA, text=" done")
        yield SessionEvent(type=EventType.TURN_END, is_final=True)


class _SlowDeltaBackend(_DeltaBackend):
    async def send_message(self, session_id: str, content: str) -> AsyncIterator[SessionEvent]:
        yield SessionEvent(type=EventType.TOOL_ACTIVITY, tool_name="Bash")
        yield SessionEvent(type=EventType.TEXT_DELTA, text="hello")
        await asyncio.sleep(0.01)
        yield SessionEvent(type=EventType.TEXT_DELTA, text=" world")
        yield SessionEvent(type=EventType.TURN_END, is_final=True)


class _CumulativeTextBackend(_DeltaBackend):
    async def send_message(self, session_id: str, content: str) -> AsyncIterator[SessionEvent]:
        yield SessionEvent(type=EventType.TEXT, text="first update")
        await asyncio.sleep(0.01)
        yield SessionEvent(type=EventType.TEXT, text="first update\n\nsecond update")
        yield SessionEvent(type=EventType.TURN_END, is_final=True)


class _CumulativeDeltaBackend(_DeltaBackend):
    async def send_message(self, session_id: str, content: str) -> AsyncIterator[SessionEvent]:
        yield SessionEvent(type=EventType.TEXT_DELTA, text="AAAAA")
        await asyncio.sleep(0.01)
        yield SessionEvent(type=EventType.TEXT_DELTA, text="AAAAABBBBB")
        await asyncio.sleep(0.01)
        yield SessionEvent(type=EventType.TEXT_DELTA, text="AAAAABBBBBCCCCC")
        yield SessionEvent(type=EventType.TURN_END, is_final=True)


class _SettingsBackend(_DeltaBackend):
    def __init__(self) -> None:
        self.service_tiers: list[tuple[str, str]] = []
        self.sent_messages: list[tuple[str, str]] = []

    async def set_session_service_tier(self, session_id: str, service_tier: str) -> None:
        self.service_tiers.append((session_id, service_tier))

    async def send_message(self, session_id: str, content: str) -> AsyncIterator[SessionEvent]:
        self.sent_messages.append((session_id, content))
        yield SessionEvent(type=EventType.TEXT_DELTA, text="ok")
        yield SessionEvent(type=EventType.TURN_END, is_final=True)


@pytest.mark.asyncio
async def test_non_verbose_posts_only_final_message(db: Database, mock_say: AsyncMock, mock_client: AsyncMock) -> None:
    thread = Thread(
        thread_ts="1234567890.000101",
        channel_id="C123",
        session_id="sess-quiet",
        verbose=False,
        text_delta_only=False,
    )
    async with db._connect() as conn:
        await queries.upsert_thread(conn, thread)

    coordinator = ThreadCoordinator(_DeltaBackend(), db)
    await coordinator._process_message(
        "1234567890.000101",
        "C123",
        "hi",
        mock_say,
        mock_client,
        user_id="U123",
    )

    assert mock_say.call_count == 1
    mock_say.assert_called_once_with(text="<@U123> hello world", thread_ts="1234567890.000101")
    mock_client.chat_update.assert_not_called()


@pytest.mark.asyncio
async def test_non_verbose_command_with_prompt_posts_only_final_message(
    db: Database, mock_say: AsyncMock, mock_client: AsyncMock
) -> None:
    coordinator = ThreadCoordinator(_DeltaBackend(), db)

    await coordinator.handle_user_message(
        "1234567890.000102",
        "C123",
        "non-verbose hi",
        mock_say,
        mock_client,
        user_id="U123",
    )
    await coordinator._active["1234567890.000102"]

    assert mock_say.call_count == 1
    mock_say.assert_called_once_with(text="<@U123> hello world", thread_ts="1234567890.000102")


@pytest.mark.asyncio
async def test_text_delta_command_streams_text_without_activity_updates(
    db: Database, mock_say: AsyncMock, mock_client: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(coordinator_module, "STREAM_FIRST_POST_DELAY", 0)
    monkeypatch.setattr(coordinator_module, "STREAM_DEBOUNCE_DELAY", 0)

    coordinator = ThreadCoordinator(_SlowDeltaBackend(), db)

    await coordinator.handle_user_message(
        "1234567890.000105",
        "C123",
        "text-delta hi",
        mock_say,
        mock_client,
        user_id="U123",
    )
    await coordinator._active["1234567890.000105"]

    posted_texts = [call.kwargs["text"] for call in mock_say.call_args_list]
    assert posted_texts == ["hello", " world\n\n:white_check_mark:"]
    mock_client.chat_update.assert_not_called()

    async with db._connect() as conn:
        thread = await queries.get_thread(conn, "1234567890.000105")
    assert thread is not None
    assert thread.verbose is False
    assert thread.text_delta_only is True


@pytest.mark.asyncio
async def test_fast_command_sets_codex_fast_service_tier(
    db: Database, mock_say: AsyncMock, mock_client: AsyncMock
) -> None:
    backend = _SettingsBackend()
    coordinator = ThreadCoordinator(backend, db)

    await coordinator.handle_user_message(
        "1234567890.000107",
        "C123",
        "mode fast",
        mock_say,
        mock_client,
        user_id="U123",
    )

    async with db._connect() as conn:
        thread = await queries.get_thread(conn, "1234567890.000107")

    assert thread is not None
    assert thread.service_tier == "fast"
    assert backend.service_tiers == [(thread.session_id, "fast")]
    mock_say.assert_called_once_with(
        text=":zap: Codex service tier set to `fast`",
        thread_ts="1234567890.000107",
    )


@pytest.mark.asyncio
async def test_fast_command_with_prompt_runs_remaining_message(
    db: Database, mock_say: AsyncMock, mock_client: AsyncMock
) -> None:
    backend = _SettingsBackend()
    coordinator = ThreadCoordinator(backend, db)

    await coordinator.handle_user_message(
        "1234567890.000108",
        "C123",
        "/fast inspect status",
        mock_say,
        mock_client,
        user_id="U123",
    )
    await coordinator._active["1234567890.000108"]

    assert backend.sent_messages == [(backend.service_tiers[0][0], "inspect status")]
    assert backend.service_tiers == [(backend.service_tiers[0][0], "fast")] * 2


@pytest.mark.asyncio
async def test_text_delta_mode_posts_only_new_text_from_cumulative_delta_events(
    db: Database, mock_say: AsyncMock, mock_client: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(coordinator_module, "STREAM_FIRST_POST_DELAY", 0)
    monkeypatch.setattr(coordinator_module, "STREAM_DEBOUNCE_DELAY", 0)

    coordinator = ThreadCoordinator(_CumulativeDeltaBackend(), db)

    await coordinator.handle_user_message(
        "1234567890.000106",
        "C123",
        "text-delta hi",
        mock_say,
        mock_client,
        user_id="U123",
    )
    await coordinator._active["1234567890.000106"]

    posted_texts = [call.kwargs["text"] for call in mock_say.call_args_list]
    assert posted_texts == ["AAAAA", "BBBBB", "CCCCC\n\n:white_check_mark:"]
    mock_client.chat_update.assert_not_called()


@pytest.mark.asyncio
async def test_non_verbose_tool_confirmation_followup_posts_final_message(
    db: Database, mock_say: AsyncMock, mock_client: AsyncMock
) -> None:
    thread = Thread(
        thread_ts="1234567890.000103",
        channel_id="C123",
        session_id="sess-quiet",
        user_id="U123",
        verbose=False,
        text_delta_only=False,
    )
    async with db._connect() as conn:
        await queries.upsert_thread(conn, thread)
        await queries.add_pending_confirmation(
            conn,
            tool_use_id="tool-quiet",
            thread_ts="1234567890.000103",
            tool_name="bash",
            tool_input={"command": "echo ok"},
        )

    coordinator = ThreadCoordinator(_ConfirmationBackend(), db)
    await coordinator.handle_tool_confirmation(
        "tool-quiet",
        "1234567890.000103",
        allowed=False,
        say=mock_say,
        client=mock_client,
    )

    assert mock_say.call_count == 1
    mock_say.assert_called_once_with(text="<@U123> denied done", thread_ts="1234567890.000103")


@pytest.mark.asyncio
async def test_non_verbose_post_summary_tool_does_not_post_mid_turn(
    db: Database, mock_say: AsyncMock, mock_client: AsyncMock
) -> None:
    thread = Thread(
        thread_ts="1234567890.000104",
        channel_id="C123",
        session_id="sess-quiet",
        verbose=False,
        text_delta_only=False,
    )
    async with db._connect() as conn:
        await queries.upsert_thread(conn, thread)

    coordinator = ThreadCoordinator(_DeltaBackend(), db)
    result = await coordinator._handle_custom_tool(
        SessionEvent(
            type=EventType.TOOL_USE,
            tool_name="post_summary",
            tool_input={"summary": "quiet summary", "status": "completed"},
        ),
        "1234567890.000104",
        mock_say,
        mock_client,
    )

    assert result == "Summary captured for final response: quiet summary"
    mock_say.assert_not_called()
