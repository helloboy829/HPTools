import asyncio
import unittest

from aiperf.engine.models import RequestResult, RequestStatus, RunStatus
from aiperf.engine.runner import FixedConcurrencyRunner
from aiperf.models.execution import ExecutionConfig


def make_config(request_count: int = 20, concurrency: int = 4) -> ExecutionConfig:
    return ExecutionConfig(request_count, concurrency, 1.0, 2.0)


class FixedConcurrencyRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_schedules_fixed_count_without_exceeding_concurrency(self) -> None:
        in_flight = 0
        observed_max = 0

        async def operation(index: int) -> RequestResult:
            nonlocal in_flight, observed_max
            in_flight += 1
            observed_max = max(observed_max, in_flight)
            await asyncio.sleep(0.001)
            in_flight -= 1
            return RequestResult(index, RequestStatus.COMPLETED, 1.0, True)

        summary, results = await FixedConcurrencyRunner(make_config()).run(operation)

        self.assertEqual(len(results), 20)
        self.assertEqual(summary.requested_count, 20)
        self.assertEqual(summary.scheduled_count, 20)
        self.assertEqual(summary.completed_count, 20)
        self.assertEqual(summary.success_count, 20)
        self.assertLessEqual(observed_max, 4)
        self.assertLessEqual(summary.max_in_flight, 4)
        self.assertEqual([result.index for result in results], list(range(1, 21)))

    async def test_operation_failure_is_retained_and_other_work_completes(self) -> None:
        async def operation(index: int) -> RequestResult:
            if index == 2:
                raise RuntimeError("private detail must not escape")
            return RequestResult(index, RequestStatus.COMPLETED, 1.0, True)

        summary, results = await FixedConcurrencyRunner(make_config(3, 2)).run(operation)

        self.assertEqual(len(results), 3)
        self.assertEqual(summary.completed_count, 3)
        self.assertEqual(summary.success_count, 2)
        self.assertEqual(summary.failed_count, 1)
        failed = next(result for result in results if result.index == 2)
        self.assertEqual(failed.status, RequestStatus.FAILED)
        self.assertEqual(failed.error_code, "ENGINE_OPERATION_ERROR")

    async def test_completed_business_failure_counts_as_failed_not_success(self) -> None:
        async def operation(index: int) -> RequestResult:
            return RequestResult(index, RequestStatus.COMPLETED, 1.0, index != 1)

        summary, _ = await FixedConcurrencyRunner(make_config(2, 1)).run(operation)

        self.assertEqual(summary.completed_count, 2)
        self.assertEqual(summary.success_count, 1)
        self.assertEqual(summary.failed_count, 1)

    async def test_pre_cancelled_run_schedules_no_work(self) -> None:
        cancel_event = asyncio.Event()
        cancel_event.set()
        calls: list[int] = []

        async def operation(index: int) -> RequestResult:
            calls.append(index)
            return RequestResult(index, RequestStatus.COMPLETED, 1.0, True)

        summary, results = await FixedConcurrencyRunner(make_config()).run(operation, cancel_event)

        self.assertEqual(calls, [])
        self.assertEqual(results, ())
        self.assertEqual(summary.scheduled_count, 0)
        self.assertEqual(summary.status, RunStatus.CANCELLED)

    async def test_cancellation_stops_new_work_and_keeps_in_flight_results(self) -> None:
        cancel_event = asyncio.Event()
        started = 0
        two_started = asyncio.Event()
        release = asyncio.Event()

        async def operation(index: int) -> RequestResult:
            nonlocal started
            started += 1
            if started == 2:
                two_started.set()
            await release.wait()
            return RequestResult(index, RequestStatus.COMPLETED, 1.0, True)

        run_task = asyncio.create_task(FixedConcurrencyRunner(make_config(10, 2)).run(operation, cancel_event))
        await asyncio.wait_for(two_started.wait(), timeout=1.0)
        cancel_event.set()
        await asyncio.sleep(0)
        release.set()
        summary, results = await asyncio.wait_for(run_task, timeout=1.0)

        self.assertEqual(started, 2)
        self.assertEqual(len(results), 2)
        self.assertEqual(summary.scheduled_count, 2)
        self.assertEqual(summary.completed_count, 2)
        self.assertEqual(summary.status, RunStatus.CANCELLED)

    async def test_allows_the_approved_maximum_concurrency(self) -> None:
        async def operation(index: int) -> RequestResult:
            await asyncio.sleep(0)
            return RequestResult(index, RequestStatus.COMPLETED, 1.0, True)

        summary, _ = await FixedConcurrencyRunner(make_config(100, 100)).run(operation)

        self.assertEqual(summary.scheduled_count, 100)

    async def test_cancelling_runner_task_cleans_up_in_flight_operations(self) -> None:
        operation_started = asyncio.Event()
        operation_cancelled = asyncio.Event()

        async def operation(index: int) -> RequestResult:
            operation_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                operation_cancelled.set()
                raise
            return RequestResult(index, RequestStatus.COMPLETED, 1.0, True)

        run_task = asyncio.create_task(FixedConcurrencyRunner(make_config(10, 2)).run(operation))
        await asyncio.wait_for(operation_started.wait(), timeout=1.0)
        run_task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await run_task
        self.assertTrue(operation_cancelled.is_set())


if __name__ == "__main__":
    unittest.main()
