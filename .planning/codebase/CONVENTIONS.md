# Coding Conventions

**Analysis Date:** 2026-04-06

## Naming Patterns

**Files:**
- Python modules and packages use **snake_case** (e.g. `app/scrapers/states/california.py`, `app/config.py`).
- One scraper module per state under `app/scrapers/states/`.
- ORM-oriented names under `app/models/` (table-oriented filenames per `AGENTS.md`).

**Functions:**
- **snake_case** for functions and methods across `app/`, `agent/`, `watchdog/`.

**Variables:**
- **snake_case** for locals and parameters; type hints used in settings and public APIs (see `app/config.py`).

**Types / classes:**
- **PascalCase** for Pydantic settings and ORM models (e.g. `Settings` in `app/config.py`).

**Prescriptive (project rules):**
- Follow C-01 in `.kiln/docs/arch-constraints.md` and `AGENTS.md`: short, single-purpose functions with docstrings; no metaprogramming, no dynamic imports, no clever abstractions.

## Code Style

**Formatting:**
- **Not detected:** No `ruff.toml`, `[tool.ruff]`, `black` config, or `.editorconfig` in the repository root. Rely on Python 3.12+ syntax and consistent style matching existing modules.

**Linting:**
- **Not detected:** No ESLint/Biome (C-14: Python only). No configured mypy or ruff in `pyproject.toml`.

**Type hints:**
- Present on settings and many internal APIs (e.g. `app/config.py`, `app/logging.py` return types). Extend the same style for new code.

## Import Organization

**Order (observed in `app/`):**
1. Standard library
2. Third-party (e.g. `structlog`, `pydantic_settings`, `fastapi`)
3. First-party `app.*` / `agent.*` / `watchdog.*`

**Path aliases:**
- **Not detected:** No `src` layout or import path rewrites; packages are `app`, `agent`, `watchdog` per `pyproject.toml` `[tool.setuptools.packages.find]`.

**Mandatory patterns (`AGENTS.md`, C-06/C-07):**
- Pipeline code imports the abstract export surface only: `app.export.adapter` — never GHL-specific modules directly.
- `watchdog/` must not import from `app/` or `agent/`.
- Configuration: use `app.config` / pydantic-settings (`Settings`); do not read raw `os.environ` in application logic.

## Error Handling

**Patterns:**
- **Pydantic `ValidationError`:** Required settings missing → fail fast (see tests in `tests/unit/test_config.py`).
- **Domain errors:** Raised exceptions consumed by callers or tests (e.g. `WaterfallExhaustedError` in `app/enrichment/waterfall.py`, asserted in `tests/unit/test_waterfall.py` and `tests/integration/test_e2e_pipeline.py`).
- **HTTP / I/O:** Scrapers and async code use async patterns; tests mock `httpx` or session behavior with `AsyncMock` (e.g. `tests/unit/test_scraper_base.py`, `tests/unit/test_state_scrapers.py`).

**Prescriptive:**
- Prefer explicit exceptions over silent failures for pipeline stages that affect compliance or export (align with C-02).

## Logging

**Framework:** `structlog` via `app/logging.py`.

**Patterns:**
- Call `configure_logging()` where the process starts (application entrypoints).
- Obtain loggers with `get_logger("<component>")` from `app/logging.py`; bind **component**, and on meaningful events include **status**, **error_type**, and **context** as required by `AGENTS.md` / C-01.

**Example (production-style binding, mirrored in tests):**

```python
from app.logging import configure_logging, get_logger

configure_logging()
logger = get_logger("test_component")
logger.info("test message", status="ok", error_type=None, context="unit_test")
```

Reference: `tests/unit/test_logging.py` validates JSON output and bound fields.

## Comments

**When to comment:**
- Module-level docstrings describe purpose and constraints (`app/config.py`, `app/logging.py`).
- Test docstrings state the behavior under test (one line, imperative).

**Docstrings:**
- Use for public modules and non-obvious behavior; C-01 expects docstrings on functions — match the style in `app/logging.py` (`configure_logging`, `get_logger`).

## Function Design

**Size:** Target **under 50 lines**, single responsibility (C-01, `AGENTS.md`).

**Parameters:** Prefer explicit keyword-friendly signatures for services (e.g. job queue functions in `app/services/job_queue.py`).

**Return values:** Use clear types (`Settings` fields, async functions returning concrete models or dicts).

## Module Design

**Exports:** Import concrete symbols from submodules (e.g. `from app.services.job_queue import enqueue` in tests).

**Barrel files:** **Not used** as a strict pattern; packages are navigated by explicit submodule paths.

---

*Convention analysis: 2026-04-06*
