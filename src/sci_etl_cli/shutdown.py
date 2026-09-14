from __future__ import annotations

import asyncio
from typing import Any, Coroutine

from sci_etl_core.signals import ShutdownSignal
from sci_etl_core.state.async_base import AsyncStateManager


async def run_until_interrupted(
    run: Coroutine[Any, Any, int], shutdown: ShutdownSignal, state_manager: AsyncStateManager
) -> int | None:
    """Await ``run`` until it finishes or a shutdown signal arrives.

    A first Ctrl+C cancels the records in flight, which stay unmarked and are
    retried on the next run; a second one terminates immediately. State is
    flushed in both cases.

    Returns:
        The number of relevant records processed, or ``None`` when a signal
        cancelled the run.

    Raises:
        PipelineAborted: The run itself aborted. State is flushed first.
    """
    with shutdown.guard():
        run_task = asyncio.ensure_future(run)
        stop_task = asyncio.ensure_future(shutdown.wait())
        await asyncio.wait({run_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
        for task in (run_task, stop_task):
            task.cancel()
        await asyncio.gather(run_task, stop_task, return_exceptions=True)
    await state_manager.flush()
    if run_task.cancelled():
        return None
    return run_task.result()
