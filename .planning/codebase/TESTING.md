# Testing Patterns

**Analysis Date:** 2026-04-06

## Test Framework

**Runner:**
- **pytest** (>=8.0.0) — declared in `pyproject.toml` under `[project.optional-dependencies] dev`.
- Config: `[tool.pytest.ini_options]` in `pyproject.toml`:
  - `asyncio_mode = "auto"` (pytest-asyncio)
  - `testpaths = ["tests"]`

**Assertion library:**
- pytest built-in assertions (`assert`).

**Run commands:**

```bash
pip install -e ".[dev]"   # install project + dev deps
pytest                     # all tests under tests/ (per AGENTS.md)
pytest -x -v               # CI-style: stop on first failure, verbose (matches .github/workflows/ci.yml)
pytest tests/smoke/ -m slow -v   # slow smoke tests (documented in tests/smoke/test_scraper_smoke.py)
```

## Test File Organization

**Location:**
- Separate tree under `tests/` with subpackages `tests/unit/`, `tests/integration/`, `tests/smoke/`.
- **`tests/contract/`:** **Not detected** — no `tests/contract/` directory on disk; `AGENTS.md` describes contract tests as part of the target layout, but they are not present yet.

**Naming:**
- `test_<module_topic>.py` mirroring source areas (e.g. `tests/unit/test_config.py` for `app/config.py`, `tests/unit/test_db.py` for `app/db.py`).

**Structure:**

```
tests/
├── conftest.py
├── unit/
│   ├── test_config.py
│   ├── test_db.py
│   ├── test_job_queue.py
│   └── ...
├── integration/
│   └── test_e2e_pipeline.py
└── smoke/
    └── test_scraper_smoke.py
```

## Test Structure

**Suite organization:**
- Plain functions prefixed with `test_`; async tests use `@pytest.mark.asyncio` (auto mode still allows explicit marker where used).

**Patterns:**
- **Setup:** Autouse fixture `set_test_env` in `tests/conftest.py` sets `DATABASE_URL` and `SENTRY_DSN` via `monkeypatch` and clears LRU caches on `app.db` factories so each test sees fresh config.
- **Reload pattern:** Settings tests use `importlib.reload(app.config)` after env changes (`tests/unit/test_config.py`).
- **Assertions:** Direct `assert` on return values, call counts on mocks, and `pytest.raises` for expected failures.

**Example (async + mock):**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.job_queue import enqueue

@pytest.mark.asyncio
async def test_enqueue_creates_pending_job():
    session = AsyncMock()
    session.flush = AsyncMock()
    with patch("app.services.job_queue.JobQueue") as MockJob:
        instance = MagicMock()
        instance.id = 42
        MockJob.return_value = instance
        job_id = await enqueue(session, "scrape", {"state": "CA"}, priority=5)
        assert job_id == 42
```

Source: `tests/unit/test_job_queue.py`.

## Mocking

**Framework:** `unittest.mock` (`AsyncMock`, `MagicMock`, `patch`).

**Patterns:**
- **SQLAlchemy async session:** `AsyncMock()` for `session`, `session.execute`, `session.flush`, `session.add` (`tests/unit/test_job_queue.py`).
- **HTTP client:** `AsyncMock` for `httpx` client context manager (`__aenter__` / `__aexit__`) and `.get` (`tests/unit/test_scraper_base.py`, `tests/unit/test_state_scrapers.py`).
- **Time / env:** `monkeypatch.setenv` / `delenv` for config and compliance tests (`tests/unit/test_config.py`, `tests/unit/test_compliance.py`).
- **patch target:** Patch where the symbol is used (e.g. `patch("app.services.job_queue.JobQueue")`).

**What to mock:**
- External I/O (HTTP, DB session) in unit tests; keep tests hermetic.

**What NOT to mock (integration-style):**
- `tests/integration/test_e2e_pipeline.py` chains real pure functions (detector, scorer, waterfall with inline async stubs, dedup helpers) without a live Postgres — document as integration of **logic stages**, not full DB E2E.

## Fixtures and Factories

**Test data:**
- Inline literals and small dicts in tests; parametrize scraper classes in `tests/unit/test_state_scrapers.py`.

**Location:**
- Shared env behavior: `tests/conftest.py` only; no separate `tests/fixtures/` package **detected**.

## Coverage

**Requirements:**
- **Not enforced in CI:** `.github/workflows/ci.yml` runs `pytest -x -v` only — no `--cov` or threshold.
- **Dependency present:** `pytest-cov>=4.0.0` is listed in `pyproject.toml` optional `dev` but **not referenced** in the workflow.

**View coverage (local, optional):**

```bash
pytest --cov=app --cov-report=term-missing
```

## Test Types

**Unit tests (`tests/unit/`):**
- Isolated modules: config, db factory, logging JSON shape, job queue, scrapers, rate limiter, compliance helpers, models, waterfall, etc.

**Integration tests (`tests/integration/`):**
- `tests/integration/test_e2e_pipeline.py` — multi-stage pipeline behavior (detection, scoring, waterfall, compliance gate callable, adapter interface, dedup) without requiring a running database for all assertions.

**Smoke tests (`tests/smoke/`):**
- Live portal checks; marked `@pytest.mark.slow` and `@pytest.mark.asyncio` — intended for manual or scheduled runs, not default CI.

**E2E / contract:**
- **Playwright** is a runtime dependency in `pyproject.toml`, but **no Playwright-driven E2E test files** were found under `tests/`.
- **Contract tests directory:** missing (see above).

## Common Patterns

**Async testing:**

```python
@pytest.mark.asyncio
async def test_waterfall_fallback_behavior():
    async def source_a(**kw):
        raise ValueError("down")
    async def source_b(**kw):
        return {"phone": "555-0100"}
    # ...
```

Source: `tests/integration/test_e2e_pipeline.py`.

**Error testing:**

```python
with pytest.raises(WaterfallExhaustedError):
    await waterfall.execute()
```

Source: `tests/unit/test_waterfall.py`, `tests/integration/test_e2e_pipeline.py`.

**Parametrize:**

```python
@pytest.mark.parametrize("state_code", get_states_by_tier(1))
async def test_tier1_scraper_fetches(state_code):
    ...
```

Source: `tests/smoke/test_scraper_smoke.py`.

## CI

**Pipeline:** `.github/workflows/ci.yml` — Python 3.12, `pip install -e ".[dev]"`, `pytest -x -v` with placeholder `DATABASE_URL` and `SENTRY_DSN` (no Postgres service container in the workflow file).

---

*Testing analysis: 2026-04-06*
