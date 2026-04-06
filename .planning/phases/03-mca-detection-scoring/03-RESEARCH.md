# Phase 3: MCA Detection & Scoring - Research

**Researched:** 2026-04-06  
**Domain:** Python / SQLAlchemy async / MCA pattern matching & lead scoring  
**Confidence:** HIGH (brownfield behavior verified in-repo); MEDIUM (library choices for fuzzy matching — not yet in `pyproject.toml`)

<user_constraints>
## User Constraints (from AGENTS.md)

### C-01 — AI maintainability
Short functions (under ~50 lines, single-purpose), docstrings, tests for meaningful behavior, structlog JSON logging on meaningful state changes with fields such as `component`, `status`, `error_type`, `context`. No metaprogramming or dynamic imports for core logic.

### C-10 — Cross-state deduplication
Pipeline and data model must support **exact + fuzzy** deduplication across states. Phase 3 should persist **canonical debtor identity fields** so a later dedup milestone can merge the same business across jurisdictions without re-deriving identity from raw filing text alone.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research support |
|----|-------------|------------------|
| MCA-01 | MCA detector matches aliases (including fuzzy/shell patterns) against `mca_aliases` and filing text. | [VERIFIED: repo] Exact normalized match + shell substrings + collateral keywords exist; **no fuzzy string match** against aliases yet (`app/mca/detector.py`). |
| MCA-02 | Scoring uses position count, recency, collateral; hot/warm/cold tiers. | [VERIFIED: repo] `assign_tier`, `calculate_recency_boost`, `compute_score` in `app/mca/scorer.py`; **position count query ignores `state`** despite API taking it. |
| MCA-03 | Pipeline writes scored leads with canonical debtor identity for downstream dedup (C-10). | [VERIFIED: repo] `Lead` has `debtor_name` + `state` only — **no normalized key, EIN, or explicit canonical id**; pipeline keys “unprocessed” via `debtor_name` join only. |
| MCA-04 | Nightly alias updater runs safely and improves coverage. | [VERIFIED: repo] `run_alias_update` in `app/mca/alias_updater.py` exists; **not registered** in `app/scrapers/scheduler.py` / `create_scheduler()` (scrapes only). |
| MCA-05 | Unit tests cover matcher and scorer edge cases per master-plan acceptance. | [VERIFIED: repo] `tests/unit/test_detector.py` covers `normalize_name`, collateral, shell helpers — **not** `detect_mca` / DB-backed aliases / fuzzy; `test_scorer.py` covers pure functions — **not** async `count_positions` / `score_lead` / pipeline. |
</phase_requirements>

## Summary

The brownfield MCA package already wires **normalization → exact alias lookup (DB) → shell heuristics → collateral keywords** and a **scoring function** combining position count, recency, and collateral bonus with **hot/warm/cold** tiers. Gaps are concentrated in four areas: (1) **MCA-01** “fuzzy” is not implemented for alias matching—only exact keys on normalized names; (2) **MCA-02** `count_positions(debtor_name, state)` does not filter by `state`, so cross-state filings inflate counts; (3) **MCA-03 / C-10** the `Lead` model and pipeline do not yet persist a dedicated canonical dedup key (e.g. normalized debtor fingerprint or future entity id); (4) **MCA-04** the alias updater is a callable module, not a scheduled job; (5) **MCA-05** tests align partially with `.kiln/plans/claude_plan.md` acceptance (exact + shell) but omit fuzzy matching and async/DB paths.

**Primary recommendation:** Close requirements in this order: fix **state-scoped position counting** and **idempotent lead selection** (correctness), add **fuzzy alias matching** with a maintained library and bounded performance (MCA-01), extend **Lead + pipeline** with explicit normalized/canonical fields for C-10, register **alias updater** on APScheduler with idempotent inserts and logging, then expand **pytest** to cover `detect_mca`, scorer async paths, pipeline, and updater.

## Standard Stack

### Core

| Library | Version | Purpose | Why standard |
|---------|---------|---------|--------------|
| Python | `>=3.12` [VERIFIED: `pyproject.toml`] | Runtime | Project standard. |
| SQLAlchemy | `>=2.0` async [VERIFIED: `pyproject.toml`] | ORM, queries | Already used for `UCCFiling`, `Lead`, `MCAlias`. |
| structlog | `>=23` [VERIFIED: `pyproject.toml`] | JSON logging | C-01 alignment; already in MCA modules. |
| pytest + pytest-asyncio | `>=8` / `>=0.23` [VERIFIED: `pyproject.toml`] | Tests | `asyncio_mode = auto` for async detector/scorer tests. |

### Supporting (for planned gaps)

| Library | Version | Purpose | When to use |
|---------|---------|-------------|-------------|
| `rapidfuzz` (or `thefuzz` + `python-Levenshtein`) | *[ASSUMED]* pin at plan time via `pip index` | Fuzzy alias match with score cutoff | MCA-01; avoid hand-rolled edit distance. |

**Installation (if fuzzy matching adopted):** `pip install rapidfuzz` (add to `pyproject.toml` dependencies) — version to be pinned when implementing [ASSUMED].

**Note:** Fuzzy matching library not present in the repo today [VERIFIED: `pyproject.toml` grep — no `rapidfuzz` / `thefuzz`].

## Architecture Patterns

### Recommended layout (current — keep)

```
app/mca/
├── detector.py      # alias + heuristics
├── scorer.py        # tier + score
├── pipeline.py      # filing → lead
├── alias_updater.py # self-improvement job
└── seed_data.py     # static patterns / seed aliases
```

### Pattern: pure helpers + async I/O boundary

**What:** Keep `normalize_name`, `check_shell_patterns`, `assign_tier`, `compute_score` pure; keep DB access in `async` functions with `get_session()` context managers.  
**When:** Extending tests (sync tests for pure functions; async tests or mocked session for DB).  
**Example:** Existing split matches this pattern [VERIFIED: `app/mca/detector.py`, `app/mca/scorer.py`].

### Pattern: scheduled maintenance jobs next to scraper scheduler

**What:** Add a cron/interval job in `create_scheduler()` (or dedicated factory) calling `run_alias_update`, guarded by config flag mirroring `SCRAPER_SCHEDULER_ENABLED` pattern.  
**When:** MCA-04.  
**Anti-pattern:** Running long synchronous CPU work on the event loop thread without offload [ASSUMED: FastAPI best practice].

### Anti-patterns to avoid

- **Unscoped counts:** Using global `debtor_name` counts when product intent is per-state or per-canonical-entity [VERIFIED: bug-shaped gap in `count_positions`].
- **“Unprocessed” = no Lead with same `debtor_name`:** Ignores `state`, duplicate filings, and re-scrape cycles [VERIFIED: `get_unprocessed_filings` join condition in `app/mca/pipeline.py`].
- **Hand-rolled fuzzy matching:** High false-positive/negative risk and poor maintainability vs library-tested algorithms [ASSUMED].

## Brownfield gap table (requirements vs code)

| Req / constraint | Expected (REQUIREMENTS.md / AGENTS) | Current code [VERIFIED: repo] | Gap severity |
|------------------|--------------------------------------|-------------------------------|--------------|
| MCA-01 fuzzy | Fuzzy + shell alias matching | Shell + exact normalized only; no edit distance / token set fuzzy on `mca_aliases` | High |
| MCA-02 positions | Count reflects business rules (likely per debtor jurisdiction or canonical entity) | `count_positions` ignores `state` in `WHERE` | High |
| MCA-03 / C-10 | Canonical debtor identity on `Lead` | Only raw `debtor_name` + `state` | High (foundational for dedup phase) |
| MCA-04 nightly job | Safe scheduled alias update | `run_alias_update` exists; scheduler only registers scrapers | Medium |
| MCA-05 tests | Exact, fuzzy, shell + scoring cases | Shell/normalize/collateral + pure scorer tests only; no `detect_mca`, pipeline, updater, async DB | Medium–High |
| Idempotency | No duplicate leads for same filing/debtor | No unique constraint on (`debtor_name`,`state`); `process_filing` always inserts new `Lead` if detection passes | Medium [VERIFIED: `Lead` model + `process_filing`] |

## Don't Hand-Roll

| Problem | Don’t build | Use instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy string match vs thousands of aliases | Custom Levenshtein loops | `rapidfuzz` `process.extractOne` with score cutoff + normalize first | O(n) fuzzy without index is expensive; libraries handle edge cases [ASSUMED: ecosystem standard]. |
| Scheduling | Cron outside app only | APScheduler job in existing `create_scheduler()` | Single process deployment on Railway [VERIFIED: `app/main.py` lifespan]. |
| Cross-state entity key | Ad hoc string equality | Normalized debtor key column + later dedup service | C-10 explicit requirement. |

**Key insight:** Exact dict lookup is done; remaining MCA-01 work is **bounded fuzzy** (threshold + maybe “top-K” candidates) and **tests**, not more `if "llc" in name` branches.

## Common Pitfalls

### Pitfall 1: Silent cross-state count inflation

**What goes wrong:** Hot tiers and scores skew high when a debtor name matches filings in multiple states.  
**Why:** `count_positions` passes `state` but does not use it in the query [VERIFIED: `app/mca/scorer.py` lines 30–34].  
**How to fix:** Add `UCCFiling.state == state` (and eventually tie to canonical entity once C-10 fields exist).  
**Warning signs:** Integration tests that insert multi-state data show incorrect tiers.

### Pitfall 2: “Unprocessed filing” logic hides filings

**What goes wrong:** Any existing `Lead` with the same `debtor_name` causes `get_unprocessed_filings` to skip new filings for other states or new MCA events.  
**Why:** `outerjoin(Lead, UCCFiling.debtor_name == Lead.debtor_name)` without state or filing id [VERIFIED: `app/mca/pipeline.py` lines 27–29].  
**How to fix:** Track processing per `UCCFiling.id` (flag or join table) or composite (`debtor_name`, `state`, `filing_number`).

### Pitfall 3: Alias updater data quality

**What goes wrong:** Auto-added aliases from `lead_score >= 30` may encode noisy secured-party strings as canonical names.  
**Why:** `canonical_lender_name=party_name` on auto insert [VERIFIED: `app/mca/alias_updater.py` lines 77–80].  
**How to fix:** Human-review queue, lower confidence, dedup by normalized key, cap inserts per run.

### Pitfall 4: Fuzzy matching false positives

**What goes wrong:** Legitimate banks match short aliases.  
**Why:** Aggressive thresholds on normalized strings.  
**How to fix:** Minimum token length, weighted partial ratio, require collateral or shell signal for borderline scores [ASSUMED].

## Code Examples

### Current exact-match path (reference)

```python
# [VERIFIED: app/mca/detector.py — conceptual excerpt]
normalized = normalize_name(secured_party)
if normalized in alias_map:
    canonical, confidence = alias_map[normalized]
    return True, canonical, confidence
```

### Planned state filter for counts (illustrative)

```python
# [ASSUMED pattern — not yet in repo]
select(func.count(UCCFiling.id)).where(
    UCCFiling.debtor_name == debtor_name,
    UCCFiling.state == state,
)
```

## State of the Art

| Old approach | Current approach | Notes |
|--------------|------------------|-------|
| Regex-only lenders | DB-backed `mca_aliases` + seed | [VERIFIED: repo] |
| Single-string debtor identity | (Needed) normalized + future fuzzy dedup | C-10 [VERIFIED: AGENTS.md] |

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|-------|---------|----------------|
| A1 | `rapidfuzz` is the preferred fuzzy library for Python MCA matching | Standard Stack | Wrong lib choice → replan dependency |
| A2 | Position count should be scoped by `UCCFiling.state` | Pitfalls | If product wants national count, scorer change would revert filter |
| A3 | Nightly alias job belongs in pipeline APScheduler | Architecture | Could belong to worker service — would change deployment tasks |

## Open Questions

1. **Canonical debtor key:** What field(s) will dedup use (normalized name only, EIN, address hash)?  
   - *Known:* C-10 needs fuzzy + exact across states.  
   - *Unclear:* Whether phase 3 must add columns or only hooks.  
   - *Recommendation:* Add nullable `debtor_name_normalized` (and document future `canonical_business_id`) in phase 3 if migration scope allows.

2. **MCA detection “positive” on collateral alone:** Is `confidence=0.5` collateral path acceptable for lead creation volume?  
   - *Recommendation:* Product threshold config in `app/config.py` [ASSUMED].

## Environment Availability

> Shell probing was not run in this session (per instructions). Treat as planner checklist.

| Dependency | Required by | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| PostgreSQL | Async integration tests / pipeline | — | — | SQLite not used — keep Postgres for parity [ASSUMED] |
| Python 3.12+ | Project | — | — | — |

## Validation Architecture

> `workflow.nyquist_validation` is **true** [VERIFIED: `.planning/config.json`].

### Test framework

| Property | Value |
|----------|-------|
| Framework | pytest `>=8` [VERIFIED: `pyproject.toml`] |
| Config file | `[tool.pytest.ini_options]` in `pyproject.toml` |
| Quick run (unit, default) | `pytest tests/unit/test_detector.py tests/unit/test_scorer.py -q` |
| Full suite | `pytest` |
| Integration (Postgres) | `pytest -m integration` [VERIFIED: marker defined in `pyproject.toml`] |

### Phase requirements → test map

| Req ID | Behavior | Test type | Automated command | File exists? |
|--------|----------|-----------|-------------------|--------------|
| MCA-01 | Exact + shell + fuzzy alias detection | unit / integration | `pytest tests/unit/test_detector.py -q` (extend); add `test_detect_mca_*` | Partial — extend |
| MCA-02 | Tier + score + **state-scoped** counts | unit + integration | `pytest tests/unit/test_scorer.py -q` (extend); add async DB tests | Partial — extend |
| MCA-03 | Pipeline persists identity fields | integration | `pytest tests/integration/test_mca_pipeline.py` (to add) | ❌ Wave 0 |
| MCA-04 | Alias updater idempotent / safe | integration | `pytest tests/integration/test_alias_updater.py` (to add) | ❌ Wave 0 |
| MCA-05 | Master-plan edge cases | unit | `pytest tests/unit/test_detector.py tests/unit/test_scorer.py -q` | Partial |

### Sampling rate

- **Per task:** `pytest tests/unit/test_detector.py tests/unit/test_scorer.py -q` (or narrowed path).  
- **Phase gate:** `pytest` full green before `/gsd-verify-work`.

### Wave 0 gaps

- [ ] Async tests for `detect_mca` with mocked `load_alias_map` or test DB fixtures.  
- [ ] Tests for `count_positions` / `score_lead` with DB reflecting `state` filter.  
- [ ] `tests/integration/test_mca_pipeline.py` — filing → lead, idempotency.  
- [ ] Scheduler registration test or smoke that job is registered when enabled (MCA-04).  
- [ ] Fuzzy matcher tests once library chosen (MCA-01 / MCA-05).

## Security Domain

| ASVS area | Applies | Note |
|-----------|---------|------|
| V5 Input validation | Yes | Filing text drives matching; bound regex/fuzzy work, avoid ReDoS in custom patterns [ASSUMED]. |
| V9 Logging | Yes | Do not log full PII beyond operational need; structlog already used [VERIFIED: `app/mca/scorer.py` logs debtor name]. |

| Pattern | STRIDE | Mitigation |
|---------|--------|------------|
| SQL injection | Tampering | SQLAlchemy parameterized queries [VERIFIED: current code uses `select().where(...)`]. |
| Alias poisoning (updater) | Tampering | Validate sources, rate-limit inserts, manager review for high-impact aliases [ASSUMED]. |

## Sources

### Primary (HIGH confidence)

- Repository files: `app/mca/detector.py`, `app/mca/scorer.py`, `app/mca/pipeline.py`, `app/mca/alias_updater.py`, `app/models/lead.py`, `app/models/filing.py`, `app/scrapers/scheduler.py`, `pyproject.toml`, `.planning/REQUIREMENTS.md`, `.kiln/plans/claude_plan.md` (Milestone 3 bullets).

### Secondary

- `AGENTS.md` / workspace rules — C-01, C-10.

### Tertiary

- Fuzzy library choice and threshold tuning — [ASSUMED] pending benchmark and product approval.

## Metadata

**Confidence breakdown**

- Standard stack: HIGH for existing deps; MEDIUM for new fuzzy package.  
- Architecture: HIGH (matches on-disk layout).  
- Pitfalls: HIGH (key bugs identified in source).

**Research date:** 2026-04-06  
**Valid until:** ~2026-05-06 (revisit if scoring or dedup architecture changes).

---

## RESEARCH COMPLETE

**Phase:** 3 — MCA detection & scoring  
**Confidence:** HIGH for gap analysis; MEDIUM for fuzzy-library and dedup field final shape.

### Key findings

- Exact normalized alias matching, shell patterns, and collateral keywords are implemented; **fuzzy alias matching is not**.  
- **`count_positions` ignores `state`** — likely violates MCA-02 intent.  
- **`Lead` lacks explicit canonical dedup fields** beyond raw `debtor_name` / `state` (MCA-03 / C-10).  
- **Alias updater is not scheduled** in APScheduler (MCA-04).  
- **Tests omit** async `detect_mca`, DB integration, pipeline, fuzzy cases (MCA-05 vs master-plan).

### File created

`.planning/phases/03-mca-detection-scoring/03-RESEARCH.md`

### Ready for planning

Planner can derive tasks: state-scoped counts, processing cursor/idempotency, fuzzy matcher dependency + tests, `Lead` migration for normalized key, scheduler job + config, expanded pytest coverage.
