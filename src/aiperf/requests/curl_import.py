"""Parse a deliberately small, safe subset of cURL request text."""

from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from aiperf.errors import AIperfError
from aiperf.requests.models import (
    BodyKind,
    MultipartPart,
    NameValue,
    RequestBody,
    RequestSpec,
    RequestStep,
)


class CurlImportError(AIperfError):
    """A safe, credential-free cURL import diagnostic."""

    def __init__(self) -> None:
        super().__init__("CURL_IMPORT_REJECTED", "cURL command could not be safely imported")


@dataclass(frozen=True, slots=True)
class CurlImportResult:
    request: RequestSpec
    warnings: tuple[str, ...] = ()
    credential_refs: tuple[str, ...] = ()


_OPTIONS_WITH_VALUE = {
    "-X": "request",
    "--request": "request",
    "-H": "header",
    "--header": "header",
    "--url": "url",
    "-d": "data_file",
    "--data": "data_file",
    "--data-raw": "data",
    "--data-binary": "binary",
    "-F": "form",
    "--form": "form",
}
_SENSITIVE_NAME = re.compile(r"(?:authorization|cookie|token|secret|password|api[-_]?key|signature)", re.I)
_SAFE_SECRET_CHARS = re.compile(r"[^A-Za-z0-9_]+")
def _reject() -> CurlImportError:
    return CurlImportError()


def _secret_name(name: str) -> str:
    normalized = _SAFE_SECRET_CHARS.sub("_", name.upper()).strip("_")
    return normalized or "IMPORTED_SECRET"


def _safe_value(name: str, value: str, credential_refs: set[str]) -> tuple[str, bool]:
    if _SENSITIVE_NAME.search(name):
        secret = _secret_name(name)
        credential_refs.add(secret)
        return "{{secrets." + secret + "}}", True
    return value, False


def _contains_shell_control(command: str) -> bool:
    quote: str | None = None
    index = 0
    while index < len(command):
        char = command[index]
        if char == "\\" and quote != "'":
            index += 2
            continue
        if quote is not None:
            if char == quote:
                quote = None
            elif quote == '"' and (char == "`" or command.startswith("$(", index)):
                return True
            index += 1
            continue
        if char in {"'", '"'}:
            quote = char
            index += 1
            continue
        if char in "|&;><`" or command.startswith("$(", index):
            return True
        index += 1
    return False


def _redact_json(value: object, credential_refs: set[str]) -> object:
    if isinstance(value, dict):
        redacted: dict[str, object] = {}
        for key, item in value.items():
            if isinstance(key, str) and _SENSITIVE_NAME.search(key):
                secret = _secret_name(key)
                credential_refs.add(secret)
                redacted[key] = "{{secrets." + secret + "}}"
            else:
                redacted[key] = _redact_json(item, credential_refs)
        return redacted
    if isinstance(value, list):
        return [_redact_json(item, credential_refs) for item in value]
    return value


def _split_option(token: str) -> tuple[str, str | None]:
    if token.startswith("--") and "=" in token:
        option, value = token.split("=", 1)
        return option, value
    return token, None


def _parse_form(value: str, credential_refs: set[str]) -> MultipartPart:
    if "=" not in value:
        raise _reject()
    name, content = value.split("=", 1)
    if not name or content.startswith("<") or ";type=" in content.lower():
        raise _reject()
    if content.startswith("@"):
        path = content[1:]
        if not path:
            raise _reject()
        filename = PureWindowsPath(path).name if "\\" in path else PurePosixPath(path).name
        if not filename:
            filename = "uploaded-file"
        return MultipartPart(name=name, value=path, is_file=True, filename=filename)
    content, _ = _safe_value(name, content, credential_refs)
    return MultipartPart(name=name, value=content)


def parse_curl(command: str) -> CurlImportResult:
    """Convert supported cURL request syntax into a request draft, without execution."""

    if not isinstance(command, str) or not command.strip():
        raise _reject()
    if _contains_shell_control(command):
        raise _reject()
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        raise _reject() from None
    if not tokens or tokens[0] != "curl":
        raise _reject()

    method: str | None = None
    raw_url: str | None = None
    raw_headers: list[str] = []
    raw_data: list[tuple[str, str]] = []
    raw_forms: list[str] = []
    index = 1
    while index < len(tokens):
        token = tokens[index]
        option, inline_value = _split_option(token)
        kind = _OPTIONS_WITH_VALUE.get(option)
        if kind is None:
            if token.startswith("-"):
                raise _reject()
            if raw_url is not None:
                raise _reject()
            raw_url = token
            index += 1
            continue
        if inline_value is None:
            index += 1
            if index >= len(tokens):
                raise _reject()
            value = tokens[index]
        else:
            value = inline_value
        if kind == "request":
            if method is not None:
                raise _reject()
            method = value
        elif kind == "header":
            raw_headers.append(value)
        elif kind == "url":
            if raw_url is not None:
                raise _reject()
            raw_url = value
        elif kind in {"data", "data_file", "binary"}:
            if kind in {"data_file", "binary"} and value.startswith("@"):
                raise _reject()
            raw_data.append((kind, value))
        elif kind == "form":
            raw_forms.append(value)
        index += 1

    if raw_url is None:
        raise _reject()
    try:
        split = urlsplit(raw_url)
        if (
            split.scheme not in {"http", "https"}
            or not split.netloc
            or split.username is not None
            or split.password is not None
        ):
            raise ValueError
        _ = split.port  # Trigger urllib's invalid-port validation without retaining user information.
        if any(char in raw_url for char in "\r\n\t "):
            raise ValueError
        query = tuple(
            NameValue(name, value, bool(_SENSITIVE_NAME.search(name)))
            for name, value in parse_qsl(split.query, keep_blank_values=True)
        )
    except ValueError:
        raise _reject() from None

    credential_refs: set[str] = set()
    safe_query: list[NameValue] = []
    for item in query:
        safe_value, sensitive = _safe_value(item.name, item.value, credential_refs)
        safe_query.append(NameValue(item.name, safe_value, sensitive))

    headers: list[NameValue] = []
    for raw_header in raw_headers:
        if ":" not in raw_header:
            raise _reject()
        name, value = raw_header.split(":", 1)
        name = name.strip()
        value = value.strip()
        if not name or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name):
            raise _reject()
        safe_value, sensitive = _safe_value(name, value, credential_refs)
        headers.append(NameValue(name, safe_value, sensitive))

    body = RequestBody(BodyKind.NONE)
    warnings: list[str] = []
    content_types = [header.value.lower() for header in headers if header.name.lower() == "content-type"]
    has_json_type = any("application/json" in value for value in content_types)
    has_form_type = any("application/x-www-form-urlencoded" in value for value in content_types)

    if raw_forms:
        if raw_data:
            raise _reject()
        parts = tuple(_parse_form(value, credential_refs) for value in raw_forms)
        if any(part.is_file for part in parts):
            warnings.append("Multipart file path was retained only as an import hint; select a managed file before execution.")
        body = RequestBody(BodyKind.MULTIPART, parts=parts)
    elif raw_data:
        if any(kind == "binary" for kind, _ in raw_data) and (len(raw_data) != 1 or raw_forms):
            raise _reject()
        if len(raw_data) == 1 and raw_data[0][0] == "binary":
            body = RequestBody(BodyKind.BINARY, value=raw_data[0][1])
        else:
            data_values = [value for _, value in raw_data]
            joined = "&".join(data_values)
            if has_json_type:
                try:
                    parsed = json.loads(joined)
                except (json.JSONDecodeError, TypeError):
                    raise _reject() from None
                else:
                    body = RequestBody(BodyKind.JSON, value=_redact_json(parsed, credential_refs))
            elif has_form_type:
                safe_form: list[tuple[str, str]] = []
                for name, value in parse_qsl(joined, keep_blank_values=True):
                    safe_value, _ = _safe_value(name, value, credential_refs)
                    safe_form.append((name, safe_value))
                body = RequestBody(BodyKind.FORM, value=tuple(safe_form))
            else:
                body = RequestBody(BodyKind.TEXT, value=joined)

    request_url = urlunsplit((split.scheme, split.netloc, split.path or "/", "", ""))
    if method is None:
        method = "POST" if raw_data or raw_forms else "GET"
    try:
        step = RequestStep(
            step_id="request-1",
            name="Imported cURL request",
            method=method,
            url=request_url,
            query=tuple(safe_query),
            headers=tuple(headers),
            body=body,
        )
        request = RequestSpec((step,))
    except (TypeError, ValueError):
        raise _reject() from None

    return CurlImportResult(request, tuple(warnings), tuple(sorted(credential_refs)))
