"""Tests for _iter_stream_with_timeout — per-event idle timeout on agent streams."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest

from claude_slack_bot.core.coordinator import (
    StreamIdleTimeout,
    _iter_stream_with_timeout,
)


async def _ok_stream() -> AsyncGenerator[int, None]:
    for i in range(3):
        await asyncio.sleep(0)
        yield i


async def _hanging_stream() -> AsyncGenerator[Any, None]:
    # Yield once, then hang forever on the next step.
    yield 1
    await asyncio.sleep(3600)
    yield 2  # unreachable


async def _hangs_immediately() -> AsyncGenerator[Any, None]:
    await asyncio.sleep(3600)
    yield 1  # unreachable


@pytest.mark.asyncio
async def test_passes_through_items() -> None:
    got = [item async for item in _iter_stream_with_timeout(_ok_stream(), 1.0, "t")]
    assert got == [0, 1, 2]


@pytest.mark.asyncio
async def test_raises_on_idle_after_first_item() -> None:
    agen = _hanging_stream()
    out: list[int] = []
    with pytest.raises(StreamIdleTimeout):
        async for item in _iter_stream_with_timeout(agen, 0.05, "t"):
            out.append(item)
    assert out == [1]


@pytest.mark.asyncio
async def test_raises_when_stream_never_yields() -> None:
    with pytest.raises(StreamIdleTimeout):
        async for _ in _iter_stream_with_timeout(_hangs_immediately(), 0.05, "t"):
            pass
