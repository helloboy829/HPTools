"""Immutable request definition models shared by all runtimes."""

from dataclasses import dataclass
from enum import Enum
from math import isfinite


class BodyKind(str, Enum):
    NONE = "none"
    JSON = "json"
    FORM = "form"
    MULTIPART = "multipart"
    TEXT = "text"
    BINARY = "binary"


_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})


@dataclass(frozen=True, slots=True)
class NameValue:
    name: str
    value: str
    sensitive: bool = False

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("name must not be empty")
        if "\r" in self.name or "\n" in self.name:
            raise ValueError("name must not contain line breaks")
        if not isinstance(self.value, str):
            raise ValueError("value must be a string")
        if type(self.sensitive) is not bool:
            raise ValueError("sensitive must be a boolean")


@dataclass(frozen=True, slots=True)
class MultipartPart:
    name: str
    value: str
    is_file: bool = False
    filename: str | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("multipart part name must not be empty")
        if not isinstance(self.value, str):
            raise ValueError("multipart part value must be a string")
        if type(self.is_file) is not bool:
            raise ValueError("is_file must be a boolean")
        if self.is_file and (not self.filename or not self.filename.strip()):
            raise ValueError("file multipart parts require a filename")
        if not self.is_file and self.filename is not None:
            raise ValueError("text multipart parts cannot have a filename")


@dataclass(frozen=True, slots=True)
class RequestBody:
    kind: BodyKind
    value: object | None = None
    parts: tuple[MultipartPart, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, BodyKind):
            raise ValueError("body kind must be a BodyKind")
        if not isinstance(self.parts, tuple) or any(not isinstance(part, MultipartPart) for part in self.parts):
            raise ValueError("body parts must be a tuple of MultipartPart")
        if self.kind is BodyKind.MULTIPART and not self.parts:
            raise ValueError("multipart body requires at least one part")
        if self.kind is not BodyKind.MULTIPART and self.parts:
            raise ValueError("only multipart bodies can have parts")
        if self.kind is BodyKind.NONE and self.value is not None:
            raise ValueError("none body cannot have a value")


@dataclass(frozen=True, slots=True)
class RequestStep:
    step_id: str
    name: str
    method: str
    url: str
    query: tuple[NameValue, ...] = ()
    headers: tuple[NameValue, ...] = ()
    body: RequestBody = RequestBody(BodyKind.NONE)
    timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        if not self.step_id or not self.step_id.strip():
            raise ValueError("step_id must not be empty")
        if not self.name or not self.name.strip():
            raise ValueError("step name must not be empty")
        if not isinstance(self.method, str) or self.method.upper() not in _METHODS:
            raise ValueError("unsupported HTTP method")
        object.__setattr__(self, "method", self.method.upper())
        if not self.url or not self.url.strip():
            raise ValueError("step URL must not be empty")
        if not isinstance(self.query, tuple) or any(not isinstance(item, NameValue) for item in self.query):
            raise ValueError("query must be a tuple of NameValue")
        if not isinstance(self.headers, tuple) or any(not isinstance(item, NameValue) for item in self.headers):
            raise ValueError("headers must be a tuple of NameValue")
        if not isinstance(self.body, RequestBody):
            raise ValueError("body must be a RequestBody")
        if self.timeout_seconds is not None:
            if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float)):
                raise ValueError("timeout_seconds must be a number")
            if not isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
                raise ValueError("timeout_seconds must be finite and positive")


@dataclass(frozen=True, slots=True)
class RequestSpec:
    steps: tuple[RequestStep, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.steps, tuple) or not self.steps:
            raise ValueError("request spec requires at least one step")
        if any(not isinstance(step, RequestStep) for step in self.steps):
            raise ValueError("request steps must be RequestStep values")
        ids = [step.step_id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("request step IDs must be unique")
