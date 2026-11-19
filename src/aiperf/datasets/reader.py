"""Streaming CSV, JSON-array, and JSONL test-case readers."""

import csv
import json
import re
from collections.abc import Iterator, Mapping
from math import isfinite
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TextIO

from aiperf.datasets.models import DatasetCase, DatasetFormat, DatasetReaderOptions
from aiperf.errors import AIperfError


_CASE_METADATA_FIELDS = frozenset(
    {
        "case_id",
        "component_id",
        "scenario_id",
        "payload",
        "expected",
        "source",
        "metadata",
        "asset_refs",
        "input_paths",
        "provenance",
        "values",
    }
)
_CSV_METADATA_FIELDS = _CASE_METADATA_FIELDS - {"values"}
_JSON_CHUNK_SIZE = 64 * 1024


class DatasetImportError(AIperfError):
    """Safe source-located dataset import failure."""

    def __init__(
        self,
        source: Path,
        row: int | None,
        field: str | None,
        reason: str,
    ) -> None:
        details: dict[str, object] = {"source": source.name, "reason": reason}
        if row is not None:
            details["row"] = row
        if field is not None:
            details["field"] = field
        super().__init__("DATASET_IMPORT_ERROR", "Dataset could not be imported", details)


def iter_dataset_cases(
    source: Path,
    format: DatasetFormat,
    *,
    dataset_root: Path | None = None,
    options: DatasetReaderOptions = DatasetReaderOptions(),
) -> Iterator[DatasetCase]:
    """Yield validated cases in source order without loading the whole dataset."""

    if not isinstance(source, Path):
        raise TypeError("source must be a pathlib.Path")
    if not source.is_absolute():
        raise ValueError("source must be an absolute path")
    if not isinstance(format, DatasetFormat):
        raise TypeError("format must be a DatasetFormat")
    if not isinstance(options, DatasetReaderOptions):
        raise TypeError("options must be DatasetReaderOptions")
    root = _resolve_dataset_root(source, dataset_root) if dataset_root is not None else None
    seen_ids: set[str] = set()
    try:
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            if format is DatasetFormat.CSV:
                yield from _iter_csv(source, handle, root, options, seen_ids)
            elif format is DatasetFormat.JSONL:
                yield from _iter_jsonl(source, handle, root, options, seen_ids)
            else:
                yield from _iter_json_array(source, handle, root, options, seen_ids)
    except DatasetImportError:
        raise
    except (OSError, UnicodeError, csv.Error):
        raise DatasetImportError(source, None, None, "source file could not be read") from None


def _iter_csv(
    source: Path,
    handle: TextIO,
    root: Path | None,
    options: DatasetReaderOptions,
    seen_ids: set[str],
) -> Iterator[DatasetCase]:
    reader = csv.reader(handle, strict=True)
    try:
        header = next(reader)
    except StopIteration:
        raise DatasetImportError(source, 1, None, "CSV header is missing") from None
    except csv.Error:
        raise DatasetImportError(source, reader.line_num or 1, None, "CSV header is invalid") from None

    if not header:
        raise DatasetImportError(source, reader.line_num or 1, None, "CSV header is empty")
    if any(not name or not name.strip() for name in header):
        raise DatasetImportError(source, reader.line_num or 1, None, "CSV header contains an empty field")
    if len(header) != len(set(header)):
        raise DatasetImportError(source, reader.line_num or 1, None, "CSV header contains duplicate fields")

    ordinal = 0
    while True:
        line = reader.line_num + 1
        try:
            row = next(reader)
        except StopIteration:
            return
        except csv.Error:
            raise DatasetImportError(source, line, None, "CSV row is invalid") from None

        if not row:
            if options.skip_blank_rows:
                continue
            raise DatasetImportError(source, line, None, "blank rows are disabled")
        if len(row) != len(header):
            raise DatasetImportError(source, line, None, "CSV row field count does not match the header")
        ordinal += 1
        record = dict(zip(header, row, strict=True))
        yield _build_case(source, line, ordinal, record, root, options, seen_ids, structured=False)


def _iter_jsonl(
    source: Path,
    handle: TextIO,
    root: Path | None,
    options: DatasetReaderOptions,
    seen_ids: set[str],
) -> Iterator[DatasetCase]:
    ordinal = 0
    for line, content in enumerate(handle, start=1):
        if not content.strip():
            if options.skip_blank_rows:
                continue
            raise DatasetImportError(source, line, None, "blank rows are disabled")
        try:
            record = json.loads(
                content,
                parse_constant=_reject_json_constant,
                parse_float=_parse_finite_float,
                object_pairs_hook=_reject_duplicate_object_fields,
            )
        except (json.JSONDecodeError, ValueError):
            raise DatasetImportError(source, line, None, "JSONL record is invalid") from None
        if not isinstance(record, dict):
            raise DatasetImportError(source, line, None, "JSONL record must be an object")
        ordinal += 1
        yield _build_case(source, line, ordinal, record, root, options, seen_ids)


def _iter_json_array(
    source: Path,
    handle: TextIO,
    root: Path | None,
    options: DatasetReaderOptions,
    seen_ids: set[str],
) -> Iterator[DatasetCase]:
    stream = _StreamingJsonArray(handle)
    if stream.next_non_whitespace() != "[":
        raise DatasetImportError(source, stream.current_line, "$", "JSON root must be an array")
    stream.consume()
    stream.skip_whitespace()
    if stream.next_non_whitespace() == "]":
        stream.consume()
        stream.finish(source)
        return

    ordinal = 0
    while True:
        line = stream.current_line
        try:
            record = stream.decode_value()
        except (json.JSONDecodeError, ValueError):
            raise DatasetImportError(source, stream.current_line, "$", "JSON array contains an invalid value") from None
        if not isinstance(record, dict):
            raise DatasetImportError(source, line, "$", "JSON array records must be objects")
        ordinal += 1
        yield _build_case(source, line, ordinal, record, root, options, seen_ids)

        stream.skip_whitespace()
        separator = stream.next_non_whitespace()
        if separator == ",":
            stream.consume()
            stream.skip_whitespace()
            if stream.next_non_whitespace() == "]":
                raise DatasetImportError(source, stream.current_line, "$", "JSON array has a trailing comma")
            continue
        if separator == "]":
            stream.consume()
            stream.finish(source)
            return
        raise DatasetImportError(source, stream.current_line, "$", "JSON array separator is invalid")


def _build_case(
    source: Path,
    line: int,
    ordinal: int,
    record: Mapping[str, object],
    root: Path | None,
    options: DatasetReaderOptions,
    seen_ids: set[str],
    *,
    structured: bool = True,
) -> DatasetCase:
    case_id = record.get("case_id")
    if case_id is not None and not isinstance(case_id, str):
        raise DatasetImportError(source, line, "case_id", "case_id must be a string")
    if isinstance(case_id, str) and not case_id.strip() and (structured or case_id != ""):
        raise DatasetImportError(source, line, "case_id", "case_id must not be blank")
    generated_case_id = "case_id" not in record or case_id is None or not case_id
    if generated_case_id:
        case_id = f"row-{ordinal:06d}"
    if case_id in seen_ids:
        raise DatasetImportError(source, line, "case_id", "case_id is duplicated")
    seen_ids.add(case_id)

    if structured:
        raw_values = record.get("values", {})
        if not isinstance(raw_values, dict):
            raise DatasetImportError(source, line, "values", "values must be an object")
        values = dict(raw_values)
        for name, value in record.items():
            if name in _CASE_METADATA_FIELDS:
                continue
            if name in values:
                raise DatasetImportError(source, line, f"values.{name}", "value is defined more than once")
            values[name] = value
    else:
        values = {name: value for name, value in record.items() if name not in _CSV_METADATA_FIELDS}

    input_paths = record.get("input_paths")
    _validate_paths(source, line, "input_paths", input_paths, root)
    for field in options.attachment_fields:
        value = _lookup_field(values, field)
        _validate_paths(source, line, field, value, root)
    _validate_asset_ref_paths(source, line, record.get("asset_refs"), root)

    provenance: dict[str, object] = {"source_file": source.name, "source_line": line}
    if "provenance" in record:
        provenance["source_metadata"] = record["provenance"]
    if generated_case_id:
        provenance["case_id_generated"] = True
    return DatasetCase(
        case_id=case_id,
        ordinal=ordinal,
        values=values,
        component_id=record.get("component_id"),
        scenario_id=record.get("scenario_id"),
        payload=record.get("payload"),
        expected=record.get("expected"),
        source=record.get("source"),
        metadata=record.get("metadata"),
        asset_refs=record.get("asset_refs"),
        input_paths=input_paths,
        provenance=provenance,
    )


def _resolve_dataset_root(source: Path, dataset_root: Path) -> Path:
    if not isinstance(dataset_root, Path):
        raise TypeError("dataset_root must be a pathlib.Path")
    if not dataset_root.is_absolute():
        raise ValueError("dataset_root must be an absolute path")
    try:
        root = dataset_root.resolve(strict=True)
    except (OSError, RuntimeError):
        raise DatasetImportError(source, None, None, "dataset root is unavailable") from None
    if not root.is_dir():
        raise DatasetImportError(source, None, None, "dataset root is not a directory")
    return root


def _validate_paths(
    source: Path,
    line: int,
    field: str,
    value: object,
    root: Path | None,
) -> None:
    if value is None:
        return
    if value == "":
        return
    if isinstance(value, str):
        paths = (value,)
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        paths = tuple(value)
    else:
        raise DatasetImportError(source, line, field, "attachment paths must be a string or list of strings")
    if not paths:
        return
    if root is None:
        raise DatasetImportError(source, line, field, "dataset root is required for attachment paths")

    for reference in paths:
        if not reference or "\x00" in reference:
            raise DatasetImportError(source, line, field, "attachment path is empty or invalid")
        normalized = reference.replace("\\", "/")
        windows_path = PureWindowsPath(reference)
        posix_path = PurePosixPath(normalized)
        if (
            windows_path.is_absolute()
            or windows_path.root
            or windows_path.drive
            or posix_path.is_absolute()
            or ".." in windows_path.parts
            or ".." in posix_path.parts
            or any(":" in part for part in windows_path.parts)
        ):
            raise DatasetImportError(source, line, field, "attachment path is outside the dataset root")
        try:
            resolved = (root / Path(*posix_path.parts)).resolve(strict=True)
        except (OSError, RuntimeError):
            raise DatasetImportError(source, line, field, "attachment file is unavailable") from None
        if not resolved.is_relative_to(root):
            raise DatasetImportError(source, line, field, "attachment path is outside the dataset root")
        if not resolved.is_file():
            raise DatasetImportError(source, line, field, "attachment path is not a file")


def _validate_asset_ref_paths(
    source: Path,
    line: int,
    asset_refs: object,
    root: Path | None,
) -> None:
    if not isinstance(asset_refs, list):
        return
    for index, asset_ref in enumerate(asset_refs):
        if isinstance(asset_ref, dict) and "path" in asset_ref:
            _validate_paths(source, line, f"asset_refs[{index}].path", asset_ref["path"], root)


def _lookup_field(values: Mapping[str, object], field: str) -> object | None:
    current: object = values
    for segment in field.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current


class _StreamingJsonArray:
    """Incremental JSON array decoder retaining at most the current record and a chunk."""

    def __init__(self, handle: TextIO) -> None:
        self._handle = handle
        self._decoder = json.JSONDecoder(
            parse_constant=_reject_json_constant,
            parse_float=_parse_finite_float,
            object_pairs_hook=_reject_duplicate_object_fields,
        )
        self._buffer = ""
        self._position = 0
        self._line = 1
        self._eof = False

    @property
    def current_line(self) -> int:
        return self._line + _line_break_count(self._buffer[: self._position])

    def _read_more(self) -> bool:
        chunk = self._handle.read(_JSON_CHUNK_SIZE)
        if not chunk:
            self._eof = True
            return False
        self._buffer += chunk
        return True

    def _compact(self) -> None:
        if self._position:
            consumed = self._buffer[: self._position]
            self._line += _line_break_count(consumed)
            self._buffer = self._buffer[self._position :]
            self._position = 0

    def next_non_whitespace(self) -> str | None:
        self.skip_whitespace()
        if self._position < len(self._buffer):
            return self._buffer[self._position]
        return None

    def skip_whitespace(self) -> None:
        while True:
            while self._position < len(self._buffer) and self._buffer[self._position] in " \t\r\n":
                self._position += 1
            if self._position < len(self._buffer) or self._eof:
                return
            self._compact()
            self._read_more()

    def consume(self) -> str | None:
        char = self.next_non_whitespace()
        if char is not None:
            self._position += 1
        return char

    def decode_value(self) -> object:
        while True:
            try:
                value, end = self._decoder.raw_decode(self._buffer, self._position)
                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and end == len(self._buffer)
                    and not self._eof
                ):
                    self._read_more()
                    continue
                self._position = end
                return value
            except json.JSONDecodeError as exc:
                if self._eof:
                    raise
                if not _decode_may_need_more(exc, len(self._buffer)):
                    raise
                self._compact()
                self._read_more()
            except ValueError:
                raise

    def finish(self, source: Path) -> None:
        self.skip_whitespace()
        if self._position < len(self._buffer):
            raise DatasetImportError(source, self.current_line, "$", "content follows the JSON array")


def _decode_may_need_more(error: json.JSONDecodeError, buffer_length: int) -> bool:
    if error.pos >= buffer_length:
        return True
    if error.msg.startswith("Unterminated string starting at"):
        return True
    if error.pos >= buffer_length - 2 and error.msg in {"Expecting value", "Expecting ',' delimiter"}:
        return True
    suffix = error.doc[error.pos :].strip()
    if suffix in {".", "e", "E", "e+", "e-", "E+", "E-"}:
        preceding = error.doc[: error.pos]
        if re.search(r"-?(?:0|[1-9][0-9]*)$", preceding):
            return True
    if suffix in {"-", "t", "tr", "tru", "f", "fa", "fal", "fals", "n", "nu", "nul"}:
        return True
    if error.msg == "Invalid \\uXXXX escape" and buffer_length - error.pos < 6:
        return True
    if error.msg == "Invalid \\escape" and error.pos == buffer_length - 1:
        return True
    return False


def _line_break_count(text: str) -> int:
    return text.count("\n") + text.count("\r") - text.count("\r\n")


def _reject_json_constant(value: str) -> object:
    raise ValueError("non-standard JSON constant")


def _parse_finite_float(value: str) -> float:
    result = float(value)
    if not isfinite(result):
        raise ValueError("JSON number is outside the supported finite range")
    return result


def _reject_duplicate_object_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object field")
        result[key] = value
    return result
