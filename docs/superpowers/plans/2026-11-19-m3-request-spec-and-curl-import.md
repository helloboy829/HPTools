# Request Specification and Safe cURL Import Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add validated request/workflow models and a safe cURL-to-draft parser that never executes shell commands or persists credential literals.

**Architecture:** Request models live in the shared domain layer and preserve ordered duplicate headers/query/form parts. The importer uses only Python parsing primitives, accepts a documented allowlist of cURL request options, rejects shell operators and unsupported options, and emits a draft with warnings and secret references.

**Tech Stack:** Python 3.11+, frozen dataclasses, `enum`, `shlex`, `urllib.parse`, `json`, `unittest`.

**Spec:** `docs/04_DATASET_AND_REQUESTS.md`, `docs/08_SECURITY_AND_RELIABILITY.md`.

## Global Constraints

- cURL import parses text only and never invokes a shell, process, network, or local-file read.
- Unknown options and shell operators are rejected rather than silently ignored.
- Header, query, and form fields preserve ordering and duplicate names.
- Credential-like header/query/form values are replaced with `{{secrets.NAME}}` references and values are not included in warnings/errors.
- Request models remain independent from FastAPI and HTTP transport libraries.
- Multipart file paths from cURL are represented as import hints only; they are never opened or persisted as trusted runtime paths.

---

### Task 1: Add immutable request/workflow value models

**Files:**
- Create: `src/aiperf/requests/__init__.py`
- Create: `src/aiperf/requests/models.py`
- Test: `tests/unit/test_request_models.py`

**Interfaces:**
- `BodyKind`: `none`, `json`, `form`, `multipart`, `text`, `binary`.
- Frozen `NameValue(name: str, value: str, sensitive: bool = False)`.
- Frozen `MultipartPart(name: str, value: str, is_file: bool = False, filename: str | None = None)`.
- Frozen `RequestBody(kind: BodyKind, value: object | None = None, parts: tuple[MultipartPart, ...] = ())`.
- Frozen `RequestStep(step_id, name, method, url, query=(), headers=(), body=RequestBody(NONE), timeout_seconds=None)`.
- Frozen `RequestSpec(steps: tuple[RequestStep, ...])`.

- [x] Test method normalization/validation, nonempty IDs/names/URLs/header names, positive timeout, duplicate ordered headers/query and multipart parts, and nonempty workflow steps with unique step IDs.
- [x] Run targeted tests and verify missing-model failures.
- [x] Implement the smallest immutable validated models.
- [x] Re-run targeted tests.

### Task 2: Parse safe cURL request options into a draft

**Files:**
- Create: `src/aiperf/requests/curl_import.py`
- Modify: `src/aiperf/requests/__init__.py`
- Test: `tests/unit/test_curl_import.py`

**Interfaces:**
- `CurlImportError(AIperfError)` with safe error code `CURL_IMPORT_REJECTED`.
- Frozen `CurlImportResult(request: RequestSpec, warnings: tuple[str, ...], credential_refs: tuple[str, ...])`.
- `parse_curl(command: str) -> CurlImportResult`.

Supported flags in this slice: `-X/--request`, `-H/--header`, `--url`, `-d/--data/--data-raw/--data-binary`, `-F/--form`. A first positional URL is supported. Options accepting an argument may use `--name=value` or a following token. Other flags are rejected.

- [x] Test cURL command prefix, method, URL, repeated headers, URL query, data, multipart text fields, and file-part hints.
- [x] Test JSON Content-Type detection and JSON body parsing without changing field order inside the request model's body object.
- [x] Test rejection of pipes, redirects, command substitutions, backticks, multiple shell commands, `--config`, `--next`, proxy-command, and arbitrary unknown options.
- [x] Test secret header/query/form values are replaced by secret references and do not appear in serialized results, warnings, or exceptions.
- [x] Run targeted tests and verify missing importer behavior.
- [x] Implement static tokenization with `shlex`; do not call subprocess, shell, network, or filesystem APIs.
- [x] Re-run targeted tests.

### Task 3: Verify package boundary and public API

**Files:**
- Modify: `src/aiperf/requests/__init__.py`
- Modify: `docs/04_DATASET_AND_REQUESTS.md`
- Test: `tests/unit/test_curl_import.py`
- Test: all files under `tests/unit/`

- [x] Export the validated request models and `parse_curl` from `aiperf.requests`.
- [x] Document the exact accepted cURL flags and explicitly state that `-F name=@path` only creates a file-part hint and never reads the path.
- [x] Run the complete unit suite and a source scan confirming the importer has no subprocess/network/file-opening calls.
- [x] Run `git diff --check` and review the staged scope.
