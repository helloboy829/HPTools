"""Validated dataset reader value models."""

from dataclasses import dataclass
from enum import Enum


class DatasetFormat(str, Enum):
    CSV = "csv"
    JSON = "json"
    JSONL = "jsonl"


@dataclass(frozen=True, slots=True)
class DatasetCase:
    """One ordered case; frozen fields prevent rebinding, not nested JSON mutation."""

    case_id: str
    ordinal: int
    values: dict[str, object]
    component_id: object | None
    scenario_id: object | None
    payload: object | None
    expected: object | None
    source: object | None
    metadata: object | None
    asset_refs: object | None
    input_paths: object | None
    provenance: dict[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id.strip():
            raise ValueError("case_id must be a nonempty string")
        if isinstance(self.ordinal, bool) or not isinstance(self.ordinal, int) or self.ordinal < 1:
            raise ValueError("ordinal must be a positive integer")
        if not isinstance(self.values, dict):
            raise ValueError("values must be a dictionary")
        if not isinstance(self.provenance, dict):
            raise ValueError("provenance must be a dictionary")


@dataclass(frozen=True, slots=True)
class DatasetReaderOptions:
    """Explicit policies for blank records and local attachment fields."""

    skip_blank_rows: bool = False
    attachment_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.skip_blank_rows) is not bool:
            raise ValueError("skip_blank_rows must be a boolean")
        if not isinstance(self.attachment_fields, tuple):
            raise ValueError("attachment_fields must be a tuple")
        if any(not isinstance(field, str) or not field.strip() for field in self.attachment_fields):
            raise ValueError("attachment field names must be nonempty strings")
        if len(self.attachment_fields) != len(set(self.attachment_fields)):
            raise ValueError("attachment field names must be unique")
