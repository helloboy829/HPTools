"""Field-based redaction for structured log and error values."""

from collections.abc import Mapping
import re


_SENSITIVE_NAMES = frozenset(
    {
        "authorization",
        "cookie",
        "setcookie",
        "token",
        "accesstoken",
        "refreshtoken",
        "secret",
        "clientsecret",
        "secretkey",
        "apikey",
        "password",
        "passwd",
        "signature",
        "hmac",
        "privatekey",
    }
)
_REDACTED = "[REDACTED]"


def _normalize_field_name(name: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).casefold())


def _is_sensitive_field(name: object) -> bool:
    normalized = _normalize_field_name(name)
    return normalized in _SENSITIVE_NAMES or any(
        normalized.endswith(suffix) or normalized.startswith(suffix)
        for suffix in ("token", "secret", "apikey", "password", "passwd", "signature", "privatekey")
    )


def redact_fields(value: object) -> object:
    """Return a recursively copied value with credential fields replaced.

    Free-form string content is intentionally not inspected; callers must keep
    secrets in named structured fields to receive this protection.
    """

    if isinstance(value, Mapping):
        return {
            key: _REDACTED if _is_sensitive_field(key) else redact_fields(item)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(redact_fields(item) for item in value)
    if isinstance(value, list):
        return [redact_fields(item) for item in value]
    return value
