"""Async fixed-concurrency scheduling without transport dependencies."""

import asyncio
from collections.abc import Awaitable, Callable
from time import monotonic

from aiperf.engine.models import RequestResult, RequestStatus, RunStatus, RunSummary
from aiperf.models.execution import ExecutionConfig

Operation = Callable[[int], Awaitable[RequestResult]]


class FixedConcurrencyRunner:
    """Run a fixed number of independent operations with bounded concurrency."""

    def __init__(self, config: ExecutionConfig) -> None:
        self._config = config

    async def run(
        self,
        operation: Operation,
        cancel_event: asyncio.Event | None = None,
    ) -> tuple[RunSummary, tuple[RequestResult, ...]]:
        cancel_event = cancel_event or asyncio.Event()
        pending: set[asyncio.Task[RequestResult]] = set()
        results: list[RequestResult] = []
        next_index = 1
        max_in_flight = 0
        cancellation_seen = cancel_event.is_set()

        try:
            while pending or (next_index <= self._config.request_count and not cancellation_seen):
                while (
                    not cancellation_seen
                    and len(pending) < self._config.concurrency
                    and next_index <= self._config.request_count
                ):
                    pending.add(asyncio.create_task(self._run_operation(operation, next_index)))
                    next_index += 1
                    max_in_flight = max(max_in_flight, len(pending))
                    cancellation_seen = cancel_event.is_set()

                if not pending:
                    break

                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                results.extend(task.result() for task in done)
                cancellation_seen = cancellation_seen or cancel_event.is_set()
        except asyncio.CancelledError:
            await self._cancel_pending(pending)
            raise

        results.sort(key=lambda result: result.index)
        completed_count = sum(result.status is not RequestStatus.CANCELLED for result in results)
        success_count = sum(result.success for result in results)
        failed_count = sum(
            result.status is not RequestStatus.CANCELLED and not result.success
            for result in results
        )
        cancelled_count = sum(result.status is RequestStatus.CANCELLED for result in results)
        status = RunStatus.CANCELLED if cancellation_seen else RunStatus.COMPLETED
        summary = RunSummary(
            status=status,
            requested_count=self._config.request_count,
            scheduled_count=len(results),
            completed_count=completed_count,
            success_count=success_count,
            failed_count=failed_count,
            cancelled_count=cancelled_count,
            max_in_flight=max_in_flight,
        )
        return summary, tuple(results)

    @staticmethod
    async def _cancel_pending(pending: set[asyncio.Task[RequestResult]]) -> None:
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    @staticmethod
    async def _run_operation(operation: Operation, index: int) -> RequestResult:
        started = monotonic()
        try:
            result = await operation(index)
        except asyncio.CancelledError:
            return RequestResult(
                index=index,
                status=RequestStatus.CANCELLED,
                duration_ms=(monotonic() - started) * 1000,
                success=False,
                error_code="CANCELLED",
            )
        except Exception:
            return RequestResult(
                index=index,
                status=RequestStatus.FAILED,
                duration_ms=(monotonic() - started) * 1000,
                success=False,
                error_code="ENGINE_OPERATION_ERROR",
            )

        if result.index != index:
            return RequestResult(
                index=index,
                status=RequestStatus.FAILED,
                duration_ms=(monotonic() - started) * 1000,
                success=False,
                error_code="ENGINE_RESULT_INDEX_ERROR",
            )
        return result
