---
phase: 5
plan: 03
version: 1
status: draft
wave_count: 2
created: 2026-04-06
title: DataMerch C-15 + external API error semantics + audit-safe logs
requirements: [COMPLY-03, COMPLY-07]
depends_on_plans: [01-PLAN.md]
files_touch_estimate:
  - app/compliance/gate.py
  - app/config.py
  - tests/unit/test_datamerch_fallback.py
---

# Plan 03 — DataMerch fallback + logging

## Objective

**COMPLY-03:** When **`DATAMERCH_API_KEY`** is absent, behavior is **explicitly documented** in code + README/AGENTS: **degraded mode** logs `datamerch_unconfigured` (or renamed structured keys) and **does not silently imply compliance** — operators can see warning counts in logs. Add **config flag** if needed: e.g. `COMPLIANCE_FAIL_CLOSED_WITHOUT_DATAMERCH` default `false` for MVP with loud logs, **or** document single behavior and test it.

**COMPLY-07:** All gate-related logs use structured fields; **never** log API keys, `Authorization` headers, or full vendor bodies — only `error_type` + truncated `context`.

## Threat model

| ID | Threat | Mitigation |
|----|--------|------------|
| T-5-05 | Bearer token in exception message | Catch httpx errors; log `error_type` + status code only. |
| T-5-06 | “Fail open” hides risk | Docstring + `AGENTS.md` + operator-visible warning log on every check when unconfigured. |

## UAT criteria

| UAT ID | Criterion | REQ |
|--------|-----------|-----|
| UAT-5.05 | Missing DataMerch key emits structured warning with `component` | COMPLY-03 |
| UAT-5.06 | No secret substrings in log calls in `gate.py` | COMPLY-07 |

## Dependencies between plans

- Depends on **Plan 01** orchestration.

---

## Wave 0 — Code + config

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **0.1** Refactor `check_datamerch` / DNC / Blacklist httpx paths to shared **safe error logging** helper (status code + URL host only, no query tokens). | `grep Authorization` in `gate.py` returns no log lines with raw secrets | `rg "logger\.(info|warning|error).*Authorization" app/compliance` empty |
| **0.2** Document C-15 behavior in `AGENTS.md` (1 short paragraph). | Text mentions DataMerch + missing key | manual |

---

## Wave 1 — Tests

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **1.1** Unit tests with `httpx` mocked: HTTP 500 → logged, no exception string with key material. | `pytest tests/unit/test_datamerch_fallback.py -q` | green |

---

## must_haves

1. Missing API keys produce visible structured warnings (COMPLY-03).
2. Logs pass COMPLY-07 redaction review in tests or grep gate.
