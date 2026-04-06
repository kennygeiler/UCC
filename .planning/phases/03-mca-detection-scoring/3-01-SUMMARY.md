# Plan 01 — Execution summary

**Status:** Complete  
**Requirements:** MCA-02 (scoring), MCA-05 (tests)

## Delivered

- **`count_positions`** filters by `UCCFiling.state` so position counts are not inflated across states.
- **Unit tests** for scorer semantics (tier vs score), async **`detect_mca`** paths (exact, shell, collateral, fuzzy, negative cases).
- **Integration:** `tests/integration/test_mca_scorer.py` — state-scoped counts and `score_lead` against Postgres (skipped when DB unavailable).

## Verification

- `pytest tests/unit -q` — green.
- Integration file requires live Postgres at `DATABASE_URL`.
