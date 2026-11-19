"""Structured, safe application errors."""

from collections.abc import Mapping

from aiperf.security.redaction import redact_fields


class AIperfError(Exception):
    """An expected application error with a stable code and safe details."""

    def __init__(
        self,
        code: str,
        message: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        if not code or not code.strip():
            raise ValueError("error code must not be empty")
        if not message or not message.strip():
            raise ValueError("error message must not be empty")
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details) if details is not None else None

    def to_dict(self) -> dict[str, object]:
        """Return the stable API/log representation with sensitive fields redacted."""

        result: dict[str, object] = {"code": self.code, "message": self.message}
        if self.details:
            result["details"] = redact_fields(self.details)
        return result
