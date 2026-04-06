---
phase: 3
plan: 01
version: 1
status: draft
wave_count: 3
created: 2026-04-06
title: Scorer state-scoped position counts and async MCA-05 test coverage
requirements: [MCA-02, MCA-05]
depends_on_plans: []
files_touch_estimate:
  - app/mca/scorer.py
  - tests/unit/test_scorer.py
  - tests/unit/test_detector.py
---

# Plan 01 — `count_positions` correctness and async path tests

## Objective

Fix **MCA-02** correctness: `count_positions(debtor_name, state)` must filter `UCCFiling` rows by **`state`** so hot/warm/cold tiers are not inflated by cross-state name collisions. Expand **MCA-05** with automated tests for async **`score_lead`** / `count_positions` (Postgres or session mocks per existing test patterns) and **`detect_mca`** when the alias map is injected or DB is seeded—without waiting for fuzzy matching (Plan 02).

## Security considerations

| Topic | Requirement |
|-------|-------------|
| SQL injection | Keep parameterized SQLAlchemy `where()` clauses; no string-built SQL. |
| Logging / PII | Preserve C-01: `lead_scored` may log debtor name—do not add collateral text or secured-party blobs to logs. |
| DoS | Tests must not pull unbounded alias rows; use small fixtures or mocks. |

## UAT criteria (traceability)

| UAT ID | Criterion (operator-visible) | REQ |
|--------|------------------------------|-----|
| UAT-3.01 | For a debtor with filings in two states, score/tier in state A uses only A’s filing count (not national). | MCA-02 |
| UAT-3.02 | CI proves async scorer and detector paths are covered beyond pure helper tests. | MCA-05 |

## Dependencies between plans

- **None** (foundational for accurate scores consumed by Plan 03 pipeline tests).
- **Plan 03** should execute after this plan so integration expectations match state-scoped counts.

## MCA-01–MCA-05 coverage (phase)

| Requirement | Plan(s) | Notes |
|-------------|---------|--------|
| MCA-01 | 02 | Fuzzy alias matching. |
| MCA-02 | 01, 03 | Count filter here; tier persisted on `Lead` in 03. |
| MCA-03 | 03 | Canonical fields + pipeline idempotency. |
| MCA-04 | 04 | Scheduled alias updater. |
| MCA-05 | 01, 02, 04 | Unit/async here; fuzzy in 02; scheduler/updater in 04. |

---

## Wave 0 — Fix `count_positions` state filter

**Goal:** Align implementation with docstring and MCA-02.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **0.1** In `app/mca/scorer.py`, add `UCCFiling.state == state` to the `count_positions` query (same session pattern as today). | Multi-state fixtures: count for (`"Acme LLC"`, `"TX"`) excludes `"CA"` rows. | `pytest tests/unit/test_scorer.py -x -q` |
| **0.2** Extend `tests/unit/test_scorer.py` with a focused test that inserts or mocks filings showing **without** state filter the count would differ (document intent in test name). | Test fails on old code, passes after fix. | `pytest tests/unit/test_scorer.py::test_count_positions_filters_by_state -x` (adjust to final test name) |

---

## Wave 1 — Async tests for `score_lead`

**Goal:** MCA-05 coverage for DB-backed scoring path.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **1.1** Add async test(s) for `score_lead` that assert returned `mca_position_count`, `tier`, and `lead_score` match `compute_score` / `assign_tier` for seeded `UCCFiling` rows (**integration** marker if Postgres required; align with `tests/conftest.py` patterns). | At least one test exercises `await score_lead(...)`. | `pytest tests/unit/test_scorer.py -m integration -x -q` **or** `pytest tests/integration/... -x -q` if placed in integration package |
| **1.2** If project standard keeps scorer tests in `tests/unit/`, use the same DB fixture strategy as other async integration tests (grep `pytest.mark.integration` in repo). | No hanging sessions; uses `get_session` / engine from conftest. | `pytest tests/ -k score_lead --maxfail=1 -q` |

---

## Wave 2 — Async tests for `detect_mca`

**Goal:** MCA-05 coverage for DB alias load + decision branches.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **2.1** Add tests for `detect_mca`: (a) exact normalized alias hit from `mca_aliases`; (b) shell pattern path; (c) collateral keyword path; (d) negative (no match). Prefer **seeded `MCAlias` rows** in integration tests, or refactor `detect_mca` to accept an optional `alias_map` dependency for unit tests—**do not** use `unittest.mock.patch` of `load_alias_map` if project conventions forbid it; follow existing test style in `tests/unit/test_detector.py`. | All four behaviors asserted with stable confidence expectations. | `pytest tests/unit/test_detector.py -x -q` |
| **2.2** Ensure tests run under `pytest-asyncio` (`asyncio_mode = auto` already in `pyproject.toml`). | No deprecation warnings from asyncio plugin. | `pytest tests/unit/test_detector.py -W error::DeprecationWarning -q` |

---

## Completion checklist

- [ ] `count_positions` uses `state` in `WHERE`.
- [ ] New tests fail on pre-fix scorer branch (or equivalent regression guard).
- [ ] `pytest` (or scoped paths above) green.

## Output

After execution, add the phase plan summary artifact per GSD workflow (naming convention used elsewhere in `.planning/phases/`).
