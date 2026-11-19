# Dataset Reader v1 Implementation Plan

> **For agentic workers:** Use a fresh implementation/review checkpoint per task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a dependency-free, streaming reader for CSV, JSON arrays, and JSONL that preserves test-case data and reports safe, source-located diagnostics.

**Architecture:** A standalone `aiperf.datasets` domain package parses records into frozen-shape case objects and does not perform component registration, asset storage, HTTP execution, request mapping, or evaluation. Case containers retain native mutable JSON values; later snapshot creation must copy or serialize them. CSV cells remain strings; JSON values retain native types; explicit attachment path fields are checked against a caller-provided dataset root without storing resolved absolute paths.

**Tech Stack:** Python 3.11+, standard-library `csv`, `json`, `pathlib`, frozen dataclasses, `unittest`.

**Spec:** `docs/04_DATASET_AND_REQUESTS.md`, `docs/08_SECURITY_AND_RELIABILITY.md`, `docs/09_ROADMAP_AND_ACCEPTANCE.md`, `docs/11_REAL_PROJECT_PATTERN_ANALYSIS.md`.

## Global Constraints

- Keep the runtime dependency list empty and use Python 3.11+.
- Keep the Reader independent from FastAPI, HTTP clients, storage services, and evaluation rules.
- Preserve CSV cell values as strings and JSON/JSONL native values; never auto-parse JSON-looking strings.
- Preserve case ordering, optional payload, heterogeneous expected values, source metadata, and unknown business fields.
- Read CSV/JSONL incrementally and stream JSON arrays one record at a time.
- Do not include input values or attachment path values in error messages/details.
- Resolve attachment references only beneath an explicit dataset root and reject absolute, traversal, missing, or symlink-escaping paths.
- Treat XLSX parsing, workbook mapping, empty-row policy variants, and dataset-size limits as unconfirmed; do not implement them here.

---

### Task 1: Define dataset value models and CSV reader

**Files:**
- Create: `src/aiperf/datasets/models.py`
- Create: `src/aiperf/datasets/reader.py`
- Create: `src/aiperf/datasets/__init__.py`
- Test: `tests/unit/test_dataset_reader.py`
- Modify: `docs/superpowers/plans/2026-11-19-m4-dataset-reader.md`

**Interfaces:**
- `DatasetFormat`: `csv`, `json`, `jsonl`.
- Frozen `DatasetCase(case_id: str, ordinal: int, values: dict[str, object], component_id: object | None, scenario_id: object | None, payload: object | None, expected: object | None, source: object | None, metadata: object | None, asset_refs: object | None, input_paths: object | None, provenance: dict[str, object])`.
- `DatasetImportError(AIperfError)` with code `DATASET_IMPORT_ERROR` and safe source/row/field diagnostics.
- `DatasetReaderOptions(skip_blank_rows: bool = False, attachment_fields: tuple[str, ...] = ())`.
- `iter_dataset_cases(source: Path, format: DatasetFormat, *, dataset_root: Path | None = None, options: DatasetReaderOptions = DatasetReaderOptions()) -> Iterator[DatasetCase]`.
- JSON object records may use a `values` object; other unreserved fields remain in `values`. `case_id`, `component_id`, `scenario_id`, `payload`, `expected`, `source`, `metadata`, `asset_refs`, and `input_paths` are explicit case metadata fields; `asset_refs` and `input_paths` are preserved in their original JSON types. Missing IDs are generated as `row-<ordinal>` and duplicate IDs fail.

- [x] Write tests for CSV order, strings, BOM handling, optional fields, unknown-field preservation, duplicate case IDs, malformed headers, and row-width diagnostics.
- [x] Run the targeted tests and confirm they fail because `aiperf.datasets` is missing.
- [x] Implement the value models and a row-at-a-time CSV reader with stable ordinals and duplicate-ID diagnostics.
- [x] Run the targeted tests and confirm they pass.

### Task 2: Add streaming JSON and JSONL readers

**Files:**
- Modify: `src/aiperf/datasets/reader.py`
- Test: `tests/unit/test_dataset_reader.py`

**Interfaces:**
- JSON input root is an array of objects; JSONL input is one object per nonblank line.
- JSON and JSONL preserve strings, numbers, booleans, nulls, arrays, and objects as parsed values.
- Each returned `DatasetCase.provenance` contains the source basename and 1-based source line; JSON array cases point to their first source line.

- [x] Write tests for typed JSON values, JSONL line numbers, malformed JSON/JSONL, unsupported roots/non-object rows, and strings containing serialized JSON.
- [x] Run targeted tests and confirm missing reader behavior causes failure.
- [x] Implement incremental JSON-array decoding and JSONL line iteration without reading the entire source file.
- [x] Run targeted tests and confirm they pass.

### Task 3: Validate explicitly mapped attachment paths safely

**Files:**
- Modify: `src/aiperf/datasets/reader.py`
- Test: `tests/unit/test_dataset_reader.py`

**Interfaces:**
- `input_paths` and configured top-level `attachment_fields` are validated as a single string or a list of strings when they represent local paths; their original values remain unchanged in the returned case.
- Nonempty attachment-bearing fields require `dataset_root`; returned values remain in their original relative-string form and no absolute path is persisted in `DatasetCase`.
- Only regular files inside the resolved dataset root are accepted; lexical traversal, drive/UNC/absolute paths, missing files, and symlink escape are rejected.
- Diagnostics identify source, row, field, and reason, but never echo a path or field value.

- [x] Write tests for accepted relative attachments and rejected absolute/traversal/missing/symlink-escape paths.
- [x] Run targeted tests and confirm the unsafe-path tests fail before the validator exists.
- [x] Implement path validation using `pathlib` and platform-aware Windows/POSIX path checks.
- [x] Run targeted tests and confirm they pass.

### Task 4: Document and integrate the public Reader API

**Files:**
- Modify: `src/aiperf/datasets/__init__.py`
- Modify: `docs/04_DATASET_AND_REQUESTS.md`
- Modify: `docs/09_ROADMAP_AND_ACCEPTANCE.md`
- Modify: `docs/11_REAL_PROJECT_PATTERN_ANALYSIS.md`
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-11-19-m4-dataset-reader.md`
- Test: all files under `tests/unit/`

- [x] Export the format, options, case model, import error, and iterator from `aiperf.datasets`.
- [x] Document the implemented CSV/JSON/JSONL Reader boundary, path behavior, type preservation, memory behavior, and exclusions without marking unconfirmed business choices as approved; clarify the D:\work_2026 evidence categories and stable-vs-variable project patterns in document 11.
- [x] Update the document index range in the root README to include document 11.
- [x] Run the full unit suite, `python -m pip wheel --no-deps --no-build-isolation`, `git diff --check`, and source scans confirming no third-party dependencies, HTTP calls, or unsafe path joins were introduced.
