import unittest
from math import inf, nan

from aiperf.engine.models import RequestResult, RequestStatus, RunStatus, RunSummary


class EngineModelTests(unittest.TestCase):
    def test_request_result_is_immutable(self) -> None:
        result = RequestResult(1, RequestStatus.COMPLETED, 5.0, True)

        with self.assertRaises((AttributeError, TypeError)):
            result.success = False  # type: ignore[misc]

    def test_request_result_rejects_invalid_index_and_duration(self) -> None:
        with self.assertRaises(ValueError):
            RequestResult(0, RequestStatus.COMPLETED, 1.0, True)
        with self.assertRaises(ValueError):
            RequestResult(1, RequestStatus.COMPLETED, -1.0, True)
        for duration in (nan, inf, True):
            with self.subTest(duration=duration):
                with self.assertRaises(ValueError):
                    RequestResult(1, RequestStatus.COMPLETED, duration, True)

    def test_run_summary_accepts_consistent_terminal_counts(self) -> None:
        summary = RunSummary(
            RunStatus.COMPLETED,
            requested_count=4,
            scheduled_count=4,
            completed_count=4,
            success_count=2,
            failed_count=2,
            cancelled_count=0,
            max_in_flight=2,
        )

        self.assertEqual(summary.scheduled_count, 4)

    def test_run_summary_rejects_inconsistent_counts(self) -> None:
        with self.assertRaises(ValueError):
            RunSummary(
                RunStatus.COMPLETED,
                requested_count=2,
                scheduled_count=2,
                completed_count=1,
                success_count=1,
                failed_count=1,
                cancelled_count=0,
                max_in_flight=1,
            )


if __name__ == "__main__":
    unittest.main()
