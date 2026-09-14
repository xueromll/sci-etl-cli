from __future__ import annotations

import asyncio

import pytest
from sci_etl_core.exceptions import PipelineAborted
from sci_etl_core.signals import ShutdownSignal

from sci_etl_cli.shutdown import run_until_interrupted


class FlushCounter:
    def __init__(self) -> None:
        self.flushes = 0

    async def flush(self) -> None:
        self.flushes += 1


@pytest.mark.asyncio
async def test_completed_run_returns_its_count_after_flushing():
    state = FlushCounter()

    async def run():
        return 7

    assert await run_until_interrupted(run(), ShutdownSignal(), state) == 7
    assert state.flushes == 1


@pytest.mark.asyncio
async def test_shutdown_request_cancels_the_run_and_returns_none():
    state = FlushCounter()
    shutdown = ShutdownSignal()
    started = asyncio.Event()
    cancelled: list[bool] = []

    async def run():
        started.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
        return 0

    async def request_once_started():
        await started.wait()
        shutdown.request()

    requester = asyncio.create_task(request_once_started())
    assert await run_until_interrupted(run(), shutdown, state) is None
    await requester
    assert cancelled == [True]
    assert state.flushes == 1


@pytest.mark.asyncio
async def test_aborted_run_raises_after_flushing():
    state = FlushCounter()

    async def run():
        raise PipelineAborted("Records kept failing", 1)

    with pytest.raises(PipelineAborted):
        await run_until_interrupted(run(), ShutdownSignal(), state)
    assert state.flushes == 1
