"""Validated execution settings shared by API, CLI, and Worker adapters."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    """Initial fixed-concurrency settings for one execution."""

    request_count: int
    concurrency: int
    connect_timeout_seconds: float
    request_timeout_seconds: float
    warmup_count: int = 0

    def __post_init__(self) -> None:
        for field_name in ("request_count", "concurrency", "warmup_count"):
            value = getattr(self, field_name)
            if type(value) is not int:
                raise ValueError(f"{field_name} must be an integer")

        if self.request_count < 1:
            raise ValueError("request_count must be at least 1")
        if not 1 <= self.concurrency <= 100:
            raise ValueError("concurrency must be between 1 and 100")
        if self.warmup_count < 0:
            raise ValueError("warmup_count must not be negative")

        for field_name in ("connect_timeout_seconds", "request_timeout_seconds"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value <= 0:
                raise ValueError(f"{field_name} must be a finite positive number")

        if self.connect_timeout_seconds > self.request_timeout_seconds:
            raise ValueError("connect_timeout_seconds must not exceed request_timeout_seconds")
