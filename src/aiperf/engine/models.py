"""Execution result and lifecycle models."""

from dataclasses import dataclass
from enum import Enum
from math import isfinite


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class RequestStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class RequestResult:
    index: int
    status: RequestStatus
    duration_ms: float
    success: bool
    error_code: str | None = None

    def __post_init__(self) -> None:
        if type(self.index) is not int or self.index < 1:
            raise ValueError("request index must be at least 1")
        if isinstance(self.duration_ms, bool) or not isinstance(self.duration_ms, (int, float)):
            raise ValueError("request duration must be a number")
        if not isfinite(self.duration_ms) or self.duration_ms < 0:
            raise ValueError("request duration must be finite and not negative")
        if self.status is RequestStatus.COMPLETED and self.error_code is not None:
            raise ValueError("completed request cannot have an error code")
        if self.status is not RequestStatus.COMPLETED and self.success:
            raise ValueError("non-completed request cannot be successful")


@dataclass(frozen=True, slots=True)
class RunSummary:
    status: RunStatus
    requested_count: int
    scheduled_count: int
    completed_count: int
    success_count: int
    failed_count: int
    cancelled_count: int
    max_in_flight: int

    def __post_init__(self) -> None:
        counts = (
            self.requested_count,
            self.scheduled_count,
            self.completed_count,
            self.success_count,
            self.failed_count,
            self.cancelled_count,
            self.max_in_flight,
        )
        if any(count < 0 for count in counts):
            raise ValueError("run counts must not be negative")
        if self.scheduled_count > self.requested_count:
            raise ValueError("scheduled count cannot exceed requested count")
        if self.completed_count != self.success_count + self.failed_count:
            raise ValueError("completed count must equal success plus failed counts")
        if self.scheduled_count != self.completed_count + self.cancelled_count:
            raise ValueError("scheduled count must equal completed plus cancelled counts")
        if self.max_in_flight > self.scheduled_count:
            raise ValueError("maximum in-flight count cannot exceed scheduled count")
