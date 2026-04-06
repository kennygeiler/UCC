# Phase 5: Compliance gate — Context

**Gathered:** 2026-04-06  
**Status:** Ready for planning  
**Source:** Roadmap + `.planning/REQUIREMENTS.md` + `.kiln/docs/arch-constraints.md` + `app/compliance/` (no separate discuss-phase).

## Phase boundary

Deliver **provable** four-layer compliance (C-02) with **internal DNC** semantics (C-12), **DataMerch** behavior when keys are missing (C-15), **audit rows** in `compliance_checks`, **no export bypass**, **negative tests**, and **audit-safe structured logs** (no secrets in `context`).

Out of scope: **export adapter implementation** beyond proving the gate is invoked before any campaign IO in this repo (full GHL wiring is Phase 6).

## Implementation decisions

### Locked

- **Layer order:** Internal DNC → DataMerch → DNC scrub → Blacklist Alliance (matches `ARCHITECTURE` / C-02).
- **Failure is permanent** for that lead’s export path: `compliance_status` reflects blocked state; no soft export.
- **Settings** for API keys via `app.config.Settings` only.
- **Structured logging** with required fields on state transitions (`component`, `status`, `error_type`, `context`) — extend gate logs to match.
- **`compliance_checks`** rows for every layer pass/fail per run.

### Claude’s discretion (plans must resolve)

- **DataMerch unconfigured** (C-15): today `gate.py` returns `False` (not blocked) when `DATAMERCH_API_KEY` is absent — document **explicitly** as “degraded pass with warning” vs **fail-closed**; align with product risk tolerance and add tests.
- **Lead ORM updates** in `_mark_blocked` / `_mark_compliant` must use **`session.get(Lead, id)`** merge pattern (same bug class as enrichment pipeline).
- **Manager reversal** (C-12): minimal **audit table** or `InternalDNC` append-only flag + separate `dnc_reversal_audit` table — plan chooses smallest viable schema change.
- **Export proof** (COMPLY-05): `grep` + unit test that `upsert_lead` / export entrypoint cannot run unless `compliance_status == "cleared"` or gate was run.

## Canonical references

- `.kiln/docs/arch-constraints.md` — C-02, C-12, C-15  
- `AGENTS.md` — logging conventions  
- `app/compliance/gate.py` — current orchestrator  

---

*Phase: 05-compliance-gate*
