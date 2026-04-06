---
phase: 3
plan: 02
version: 1
status: draft
wave_count: 3
created: 2026-04-06
title: Fuzzy MCA alias matching (rapidfuzz) with cutoff and performance guardrails
requirements: [MCA-01, MCA-05]
depends_on_plans: []
files_touch_estimate:
  - pyproject.toml
  - app/mca/detector.py
  - app/config.py
  - tests/unit/test_detector.py
---

# Plan 02 — Fuzzy alias matching

## Objective

Implement **MCA-01** fuzzy matching against normalized `mca_aliases` keys **after** exact normalized lookup and **before** shell/collateral fallbacks (order preserves determinism). Use **`rapidfuzz`** with a **configurable score cutoff** and **minimum normalized length** to limit false positives (per 03-RESEARCH.md pitfall: short-alias noise). Add **MCA-05** tests for fuzzy hits, near-misses below cutoff, and performance note (document O(n) scan; acceptable for current alias cardinality—if n grows, future index/plan is out of scope but add a single comment in code).

## Security considerations

| Topic | Requirement |
|-------|-------------|
| ReDoS | Use library fuzzy matchers; do not add unbounded backtracking regex on user-controlled secured-party strings. |
| Alias poisoning | Fuzzy path only selects from DB aliases; cutoff reduces acceptance of typosquatting (full governance is ops, not this plan). |
| CPU / availability | Run fuzzy pass only when exact match misses; optionally cap max alias comparisons per call with clear log if cap hit (Claude’s discretion—if added, test it). |

## UAT criteria (traceability)

| UAT ID | Criterion (operator-visible) | REQ |
|--------|------------------------------|-----|
| UAT-3.03 | Secured party strings that are minor typos of a configured alias still classify as MCA when above configured cutoff. | MCA-01 |
| UAT-3.04 | Very short or ambiguous strings do not fuzzy-match aggressively (configurable floor). | MCA-01 |
| UAT-3.05 | Regression tests lock fuzzy + exact + shell precedence. | MCA-05 |

## Dependencies between plans

- **None** (can run parallel to Plan 01 if merge conflicts avoided—coordinate `detector.py` edits).
- **Plan 04** alias updater benefits from better detection but does not block this plan.

## MCA-01–MCA-05 coverage (phase)

| Requirement | Plan(s) | Notes |
|-------------|---------|--------|
| MCA-01 | 02 | Primary fuzzy delivery. |
| MCA-02 | 01, 03 | — |
| MCA-03 | 03 | — |
| MCA-04 | 04 | — |
| MCA-05 | 01, 02, 03, 04 | Fuzzy-specific tests here; see 01/03/04 for other MCA-05 coverage. |

---

## Wave 0 — Dependency and settings

**Goal:** Pin `rapidfuzz` and expose tunables.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **0.1** Add `rapidfuzz` to project dependencies in `pyproject.toml` with a **pinned** version (check PyPI / `pip index` at implementation time). | Editable install resolves import. | `python -c "import rapidfuzz; print(rapidfuzz.__version__)"` |
| **0.2** Add pydantic-settings fields in `app/config.py` (e.g. `MCA_FUZZY_MIN_ALIAS_LEN`, `MCA_FUZZY_SCORE_CUTOFF`—use clear names) with safe defaults documented in field descriptions. | Settings load in tests with defaults. | `pytest tests/unit/test_config.py -q` **or** add a minimal config test if none exists |

---

## Wave 1 — Implement fuzzy pass in `detector.py`

**Goal:** Deterministic fuzzy match against loaded alias list.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **1.1** After building `alias_map` from `load_alias_map()`, if normalized secured party is not an exact key, run `rapidfuzz.process.extractOne` (or `fuzz.ratio`/`token_sort_ratio`—pick one strategy and **document in docstring**) against **normalized alias keys** only; require score ≥ cutoff **and** len(normalized) ≥ min length **and** consider requiring collateral or shell for borderline scores **only if** product needs it—default: score + length only per RESEARCH recommendation. | Known typo maps to same canonical as exact alias row. | `pytest tests/unit/test_detector.py -k fuzzy -x -q` |
| **1.2** Keep functions ≤50 lines (C-01); extract `_fuzzy_match_alias(...)` helper if needed. | Ruff/format passes if configured. | `ruff check app/mca/detector.py` (if in CI) |

---

## Wave 2 — Tests and performance note

**Goal:** MCA-05 + operator-visible documentation.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **2.1** Tests: fuzzy match above cutoff; below cutoff returns false MCA via alias path (shell/collateral may still match—assert isolated cases); exact match still wins over fuzzy. | Clear test names. | `pytest tests/unit/test_detector.py -x -q` |
| **2.2** Add short comment block (≤10 lines) in `detector.py` or `03-RESEARCH.md` reference in docstring: fuzzy is O(n) over aliases; acceptable for expected table size; if n > threshold, revisit indexing/batch. | Comment present; docstring or module header cites complexity. | `rg -n -F "O(n)" app/mca/detector.py` **and** `ruff check app/mca/detector.py` **and** `pytest tests/unit/test_detector.py -k fuzzy -q` |

---

## Completion checklist

- [ ] `rapidfuzz` pinned in `pyproject.toml`.
- [ ] Fuzzy path gated by settings; defaults conservative.
- [ ] Tests cover precedence and cutoff behavior.

## Output

After execution, add phase summary artifact per GSD workflow.
