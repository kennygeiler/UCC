# Phase 5: Compliance gate — Research

**Date:** 2026-04-06  
**Question:** What must change to satisfy COMPLY-01–07 given the current tree?

## RESEARCH COMPLETE

## Current implementation snapshot

| Area | File | Notes |
|------|------|--------|
| Gate | `app/compliance/gate.py` | Four layers in order; `_log_check` writes `ComplianceCheck`; `run_compliance_gate` returns bool. |
| **Bug risk** | `_mark_blocked` / `_mark_compliant` | Uses `session.add(lead)` on detached `Lead` — may not persist or may error; should `get(Lead, id)` then mutate. |
| DataMerch | `check_datamerch` | No API key → **warning** + `return False` (not blocked). **C-15** says “fallback” — must be documented + tests. |
| DNC / Blacklist | `check_dnc_scrub`, `check_blacklist_alliance` | Missing keys → warning + `return False` (pass). |
| Internal DNC | `app/compliance/internal_dnc.py` | `add_to_dnc` append-only; **no** manager reversal / audit path in code. |
| Export | `app/export/` | **No** `run_compliance_gate` import in export path yet — **COMPLY-05 gap**. |

## Validation Architecture

### Dimension 1 — Correctness

Automated tests: layer order never permutes; each layer logs exactly one `ComplianceCheck` row per `run_compliance_gate` invocation; blocked leads never marked `cleared`.

### Dimension 2 — Security

No API keys or raw headers in logs; `context` truncated and sanitized.

### Dimension 3 — Legal / policy

C-02: no code path marks export-ready without four layers evaluated for that run.

### Dimension 4 — Observability

Structured logs on block/clear with `gate` in `context` or `component=compliance_gate`.

### Dimension 5 — Maintainability

Functions under 50 lines; gate split if needed.

### Dimension 6 — Automated verification

pytest for gate, negative scenarios, export guard; optional `grep` in CI script.

### Dimension 7 — Compatibility

Async SQLAlchemy 2.0 patterns; httpx mocks in tests.

### Dimension 8 — Nyquist

Every plan task maps to `pytest` or `rg` verify command.

---

*Phase: 05-compliance-gate*
