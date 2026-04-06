# Plan 01 — Execution summary

**Status:** Complete  
**Requirements:** SCRAPE-04, SCRAPE-06 (foundation)

## Delivered

- **Pytest markers** `slow` and `smoke` in `pyproject.toml`.
- **`SCRAPER_SCHEDULER_ENABLED`** in `app/config.py` (default `true`); tests force `false` via `tests/conftest.py`.
- **FastAPI lifespan** in `app/main.py`: starts `create_scheduler()` when enabled, `shutdown(wait=True)` on exit.
- **`schedulable_state_codes()`** and scheduler loop in `app/scrapers/scheduler.py` — **Tier 4 not scheduled**.
- **Tier 4 stubs** `DC`, `NYC` in `app/scrapers/states/tier4_stubs.py` + registry entries.
- **CI** `.github/workflows/ci.yml`: `pytest -m "not slow"`.
- **Docs:** `README.md`, `AGENTS.md` (scheduler flag).
- **Tests:** `tests/unit/test_scheduler.py`.

## Verification

- `pytest -x -v -m "not slow"` — green.
