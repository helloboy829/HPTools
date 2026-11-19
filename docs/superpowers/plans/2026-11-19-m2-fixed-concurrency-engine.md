# Fixed Concurrency Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a transport-agnostic async fixed-concurrency runner that schedules a fixed number of logical operations, enforces the 1..100 concurrency limit, supports cancellation, and returns deterministic request-level results and counts.

**Architecture:** The shared Engine receives an async operation callback; it does not know FastAPI, aiohttp, datasets, credentials, or UI. A bounded worker pool schedules at most `ExecutionConfig.concurrency` operations, records each terminal result, and returns a summary. HTTP adapters will translate their own transport errors into the engine result model later.

**Tech Stack:** Python 3.11+, `asyncio`, dataclasses, enums, unittest.IsolatedAsyncioTestCase.

**Spec:** `docs/03_EXECUTION_ENGINE.md`, `docs/01_PRODUCT_REQUIREMENTS.md`, `docs/02_ARCHITECTURE.md`.

## Global Constraints

- Fixed request count + fixed concurrency is the approved first load model.
- The default and hard maximum concurrency is 100; validate on the shared model and at Engine entry.
- Automatic retries are disabled in this milestone.
- The Engine must not import FastAPI, aiohttp, SQLite, Docker, Redis, Celery, Kafka, or Ray.
- A cancellation request stops new scheduling and lets in-flight operations terminate according to the callback contract.
- Individual operation failures become results and must not discard other completed results.
- Timestamps/durations must use a monotonic clock for elapsed time; persisted UTC timestamps are a later adapter concern.

---

### Task 1: Add result and lifecycle domain models

**Files:**
- Create: `src/aiperf/engine/__init__.py`
- Create: `src/aiperf/engine/models.py`
- Test: `tests/unit/test_engine_models.py`

**Interfaces:**
- `RunStatus`: `queued`, `running`, `cancelling`, `completed`, `cancelled`, `failed`.
- `RequestStatus`: `completed`, `failed`, `cancelled`.
- Frozen `RequestResult(index, status, duration_ms, success, error_code=None)`.
- Frozen `RunSummary(status, requested_count, scheduled_count, completed_count, success_count, failed_count, cancelled_count, max_in_flight)`.

- [x] Write tests for enum values, immutable result objects, and summary count consistency for completed/success/failed/cancelled outcomes.
- [x] Run the targeted test and confirm missing-model failure.
- [x] Implement minimal frozen dataclasses and enum values; reject negative indexes, negative durations, and impossible negative counts.
- [x] Run targeted tests and confirm they pass.

### Task 2: Add fixed-concurrency runner behavior

**Files:**
- Create: `src/aiperf/engine/runner.py`
- Test: `tests/unit/test_engine_runner.py`

**Interfaces:**
- `Operation = Callable[[int], Awaitable[RequestResult]]`.
- `FixedConcurrencyRunner(config: ExecutionConfig)`.
- `await runner.run(operation, cancel_event: asyncio.Event | None = None) -> tuple[RunSummary, tuple[RequestResult, ...]]`.

- [x] Write an async test with 20 operations and concurrency 4 that tracks in-flight count, returns success results, and asserts 20 scheduled/completed and observed max in-flight <= 4.
- [x] Write a test that operation failure result is retained while other operations complete.
- [x] Write a test that a pre-set cancellation event schedules zero work and returns `cancelled`.
- [x] Write a test that cancellation during execution stops new scheduling, retains in-flight terminal results, and returns `cancelled`.
- [x] Run targeted tests and confirm failure due to missing runner.
- [x] Implement a bounded set of async operation tasks with no retries; the callback owns request-level duration measurement.
- [x] Ensure worker exceptions are converted to `RequestResult(status=failed, error_code='ENGINE_OPERATION_ERROR')`; one callback exception must not cancel unrelated work.
- [x] Ensure `max_in_flight` is measured by the runner and included in the summary.
- [x] Re-run targeted tests and confirm they pass.

### Task 3: Verify integration with existing configuration and public imports

**Files:**
- Modify: `src/aiperf/engine/__init__.py`
- Test: `tests/unit/test_engine_runner.py`
- Test: all files under `tests/unit/`

- [x] Export the engine models and runner from `aiperf.engine` without importing any Web/API dependency.
- [x] Add a test that a config with concurrency 100 runs successfully and a config with 101 cannot reach the runner because `ExecutionConfig` rejects it.
- [x] Run `PYTHONPATH=src python -m unittest discover -s tests/unit -v`.
- [x] Run a source scan confirming `src/aiperf/engine` contains no FastAPI/aiohttp/SQLite imports.
- [x] Run `git diff --check` and review that no product decisions about RPS, retries, response parsing, or credentials were added.
