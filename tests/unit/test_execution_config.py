import unittest

from aiperf.models.execution import ExecutionConfig


class ExecutionConfigTests(unittest.TestCase):
    def test_accepts_valid_low_and_maximum_concurrency(self) -> None:
        for concurrency in (1, 100):
            with self.subTest(concurrency=concurrency):
                config = ExecutionConfig(
                    request_count=1,
                    concurrency=concurrency,
                    connect_timeout_seconds=1.0,
                    request_timeout_seconds=2.0,
                    warmup_count=0,
                )
                self.assertEqual(config.concurrency, concurrency)

    def test_rejects_invalid_request_count(self) -> None:
        with self.assertRaises(ValueError):
            ExecutionConfig(0, 1, 1.0, 2.0)

    def test_rejects_concurrency_outside_supported_range(self) -> None:
        for concurrency in (0, 101):
            with self.subTest(concurrency=concurrency):
                with self.assertRaises(ValueError):
                    ExecutionConfig(1, concurrency, 1.0, 2.0)

    def test_rejects_non_positive_timeouts(self) -> None:
        for connect_timeout, request_timeout in ((0.0, 2.0), (1.0, 0.0)):
            with self.subTest(connect_timeout=connect_timeout, request_timeout=request_timeout):
                with self.assertRaises(ValueError):
                    ExecutionConfig(1, 1, connect_timeout, request_timeout)

    def test_rejects_connect_timeout_greater_than_request_timeout(self) -> None:
        with self.assertRaises(ValueError):
            ExecutionConfig(1, 1, 3.0, 2.0)

    def test_rejects_negative_warmup_count(self) -> None:
        with self.assertRaises(ValueError):
            ExecutionConfig(1, 1, 1.0, 2.0, warmup_count=-1)

    def test_is_immutable(self) -> None:
        config = ExecutionConfig(1, 1, 1.0, 2.0)
        with self.assertRaises((AttributeError, TypeError)):
            config.concurrency = 2  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
