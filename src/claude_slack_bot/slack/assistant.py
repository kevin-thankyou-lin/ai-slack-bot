from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from slack_bolt.async_app import AsyncApp
from slack_bolt.listener_matcher.async_listener_matcher import AsyncCustomListenerMatcher
from slack_bolt.middleware.assistant.async_assistant import AsyncAssistant

from ..core.coordinator import ThreadCoordinator
from ..db import queries
from .listeners import _download_files

logger = structlog.get_logger()

ASSISTANT_SURFACE = "slack_assistant"


class AssistantSay:
    """Wrap Bolt's Assistant `say` with Assistant-specific utilities."""

    def __init__(
        self,
        say: Callable[..., Awaitable[Any]],
        *,
        set_status: Callable[..., Awaitable[Any]] | None = None,
        set_title: Callable[..., Awaitable[Any]] | None = None,
    ) -> None:
        self._say = say
        self._set_status = set_status
        self._set_title = set_title

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return await self._say(*args, **kwargs)

    async def set_status(self, *args: Any, **kwargs: Any) -> Any:
        if self._set_status is None:
            return None
        return await self._set_status(*args, **kwargs)

    async def set_title(self, *args: Any, **kwargs: Any) -> Any:
        if self._set_title is None:
            return None
        return await self._set_title(*args, **kwargs)


def _assistant_thread_fields(event: dict[str, Any]) -> tuple[str, str, str]:
    assistant_thread = event.get("assistant_thread") or {}
    return (
        str(assistant_thread.get("thread_ts") or ""),
        str(assistant_thread.get("channel_id") or ""),
        str(assistant_thread.get("user_id") or ""),
    )


async def _assistant_text_from_payload(payload: dict[str, Any], client: Any) -> str:
    text = str(payload.get("text") or "")
    text = re.sub(r"<@[A-Z0-9]+>\s*", "", text).strip()

    files = payload.get("files", [])
    if files:
        file_paths = await _download_files(files, client)
        if file_paths:
            file_note = "\n".join(f"[Attached file: {p}]" for p in file_paths)
            text = f"{text}\n\n{file_note}" if text else file_note

    return text


async def _is_known_assistant_thread(payload: dict[str, Any], coordinator: ThreadCoordinator) -> bool:
    thread_ts = str(payload.get("thread_ts") or "")
    if not thread_ts:
        return False
    async with coordinator.db._connect() as db:
        thread = await queries.get_thread(db, thread_ts)
    return thread is not None and thread.surface == ASSISTANT_SURFACE


async def _set_suggested_prompts(set_suggested_prompts: Callable[..., Awaitable[Any]]) -> None:
    prompts = [
        {
            "title": "Start a task",
            "message": "Help me work through a concrete coding task.",
        },
        {
            "title": "Set working directory",
            "message": "cd <project-folder>",
        },
        {
            "title": "Switch backend",
            "message": "backend codex",
        },
        {
            "title": "Summarize status",
            "message": "Summarize what is currently happening in this conversation.",
        },
    ]
    await set_suggested_prompts(title="Start a new agent conversation", prompts=prompts)


def register_assistant(app: AsyncApp, coordinator: ThreadCoordinator) -> None:
    """Register Slack Assistant listeners alongside the legacy Slack thread UI."""
    assistant = AsyncAssistant()

    @assistant.thread_started
    async def handle_assistant_thread_started(
        payload: dict[str, Any],
        say: Callable[..., Awaitable[Any]],
        set_suggested_prompts: Callable[..., Awaitable[Any]],
        set_title: Callable[..., Awaitable[Any]],
    ) -> None:
        thread_ts, channel_id, user_id = _assistant_thread_fields(payload)
        if not thread_ts or not channel_id:
            logger.warning("assistant.thread_started.missing_fields", payload=payload)
            return

        await coordinator.mark_assistant_thread(thread_ts, channel_id, user_id=user_id)
        try:
            await set_title("New agent conversation")
            await _set_suggested_prompts(set_suggested_prompts)
        except Exception:
            logger.warning("assistant.thread_started.setup_failed", thread_ts=thread_ts)

        await say(
            text=(
                "New agent conversation ready. Send a task, or start with "
                "`cd <project-folder>`, `backend codex`, `model <name>`, or `effort <level>`."
            ),
            thread_ts=thread_ts,
        )
        logger.info("assistant.thread_started", channel=channel_id, thread_ts=thread_ts)

    async def user_message_matcher(payload: dict[str, Any]) -> bool:
        return await _is_known_assistant_thread(payload, coordinator)

    @assistant.user_message(
        matchers=[AsyncCustomListenerMatcher(app_name=assistant.app_name, func=user_message_matcher)]
    )
    async def handle_assistant_user_message(
        payload: dict[str, Any],
        say: Callable[..., Awaitable[Any]],
        client: Any,
        set_status: Callable[..., Awaitable[Any]],
        set_title: Callable[..., Awaitable[Any]],
    ) -> None:
        text = await _assistant_text_from_payload(payload, client)
        if not text:
            return

        thread_ts = str(payload.get("thread_ts") or payload.get("ts") or "")
        channel_id = str(payload.get("channel") or "")
        user_id = str(payload.get("user") or "")
        if not thread_ts or not channel_id:
            logger.warning("assistant.user_message.missing_fields", payload=payload)
            return

        await coordinator.mark_assistant_thread(thread_ts, channel_id, user_id=user_id)
        assistant_say = AssistantSay(say, set_status=set_status, set_title=set_title)
        logger.info("assistant.user_message", channel=channel_id, thread_ts=thread_ts)
        await coordinator.handle_user_message(thread_ts, channel_id, text, assistant_say, client, user_id=user_id)

    app.use(assistant)
