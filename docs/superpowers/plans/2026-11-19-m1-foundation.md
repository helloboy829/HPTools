# M1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a dependency-light Python foundation for explicit application paths, basic execution configuration, structured errors, and safe log-field redaction.

**Architecture:** Place a single shared `aiperf` package under `src/`. Keep foundational helpers independent from FastAPI, SQLite, HTTP clients, and platform shell commands. Use Python's standard library and `unittest` for this first slice.

**Tech Stack:** Python 3.11+, `pathlib`, dataclasses, `enum`, `logging`, `unittest`; setuptools packaging metadata only.

**Spec:** `docs/01_PRODUCT_REQUIREMENTS.md`, `docs/02_ARCHITECTURE.md`, `docs/03_EXECUTION_ENGINE.md`, `docs/08_SECURITY_AND_RELIABILITY.md`, `docs/AGENTS.md`.

## Global Constraints

- Python 3.11+; use `pathlib.Path` for paths.
- Use UTF-8 and support Windows Chinese paths, spaces, and backslashes.
- Do not rely on the current working directory; resolve paths from explicit application configuration.
- Core Engine must remain separate from Web/API and must not import FastAPI.
- All external input must receive model validation.
- Default maximum concurrency is 100; validate configuration on the server side.
- Do not write real secrets to logs, normal configuration exports, task ZIPs, error details, or reports.
- Do not add Redis, Celery, Kafka, Ray, MySQL, Docker, or Node.js runtime dependencies to the Windows core.

---

### Task 1: Add package metadata and the official logo to the project entry page

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Modify: `README.md`
- Existing asset: `icon/logo.png` (use only; do not alter bytes)

**Interfaces:**
- Produces importable package `aiperf` from `src/` when the project is installed.
- Python runtime dependencies remain empty for this foundation slice.

- [x] Add Python package metadata with Python `>=3.11` and package discovery under `src`.
- [x] Ignore Python caches, local virtual environments, build outputs, and local runtime data; do not ignore the project logo.
- [x] Add the project logo to the root README and preserve the architecture/documentation links.
- [x] Verify TOML parses, package discovery configuration is present, and `icon/logo.png` is referenced without modifying it.

### Task 2: Add explicit application data paths

**Files:**
- Create: `src/aiperf/__init__.py`
- Create: `src/aiperf/config.py`
- Test: `tests/unit/test_config.py`

**Interfaces:**
- `AppPaths.from_root(root: Path) -> AppPaths`
- `AppPaths.ensure_directories() -> None`
- `AppPaths` exposes `root`, `data`, `assets`, `runs`, `packages`, `temp`, and `logs` as `Path` values.

- [x] Write tests that an absolute temporary root maps every child below that root and directory creation creates all configured locations.
- [x] Write a test that a relative root is rejected instead of being interpreted relative to the process current directory.
- [x] Run `python -m unittest tests.unit.test_config -v` with `PYTHONPATH=src` and confirm the expected import/behavior failures.
- [x] Implement `AppPaths` using `pathlib.Path`; reject non-absolute roots and do not read the current working directory to invent a root.
- [x] Re-run the targeted tests and confirm they pass on the current platform.

### Task 3: Add basic validated execution settings

**Files:**
- Create: `src/aiperf/models/__init__.py`
- Create: `src/aiperf/models/execution.py`
- Test: `tests/unit/test_execution_config.py`

**Interfaces:**
- Immutable `ExecutionConfig(request_count: int, concurrency: int, connect_timeout_seconds: float, request_timeout_seconds: float, warmup_count: int = 0)`.
- Construction raises `ValueError` for invalid values; HTTP/API adapters can translate this later.

- [x] Test valid boundary values (`request_count=1`, `concurrency=1`, `concurrency=100`, positive timeouts, zero warmup).
- [x] Test rejection of request count below one, concurrency below one or above 100, non-positive timeouts, connect timeout greater than request timeout, and negative warmup.
- [x] Run `python -m unittest tests.unit.test_execution_config -v` and verify the expected missing-model failures.
- [x] Implement the smallest frozen dataclass satisfying those tests; do not add request-rate, retries, or duration modes before product confirmation.
- [x] Re-run targeted tests and the complete unit suite.

### Task 4: Add structured application errors and log-field redaction

**Files:**
- Create: `src/aiperf/errors.py`
- Create: `src/aiperf/security/__init__.py`
- Create: `src/aiperf/security/redaction.py`
- Test: `tests/unit/test_redaction.py`
- Test: `tests/unit/test_errors.py`

**Interfaces:**
- `AIperfError(code: str, message: str, details: Mapping[str, object] | None = None)` with a safe `to_dict()` representation.
- `redact_fields(value: object) -> object` recursively copies mappings/sequences and replaces values whose normalized field names identify credentials.

- [x] Test nested authorization, cookie, token, secret, password, signature, and API-key fields, including case and hyphen/underscore variants.
- [x] Test that benign fields remain unchanged, input objects are not mutated, and exception stringification does not include `details` unless explicitly formatted.
- [x] Run targeted tests and verify failures are caused by missing behavior.
- [x] Implement a small field-name-based redactor; do not claim it detects arbitrary secrets embedded in free-form text.
- [x] Verify structured error output contains only code/message/details and no traceback or environment data.

### Task 5: Verify foundation and document the local test command

**Files:**
- Modify: `README.md`
- Test: all files under `tests/unit/`

- [x] Document the dependency-free test command and explicit `PYTHONPATH=src` setup for PowerShell and POSIX shells.
- [x] Run `python -m unittest discover -s tests/unit -v` with `PYTHONPATH=src`.
- [x] Parse `pyproject.toml`, ensure the logo remains unchanged, inspect `git diff --check`, and review the changed-file list.
- [x] Confirm no pending product decision (secret provider, statistics semantics, source workbook mapping, or task package policy) was silently implemented.

## Out of Scope

HTTP transport, FastAPI routes, SQLite schema/migrations, secret storage/provider, task execution scheduler, request/cURL parsing, dataset import, package import/export, Worker container, and UI are later milestones. This plan does not decide pending product questions in those areas.
