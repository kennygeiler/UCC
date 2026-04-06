# Plan 03 — Execution summary

**Status:** Complete  
**Requirements:** MCA-03 (canonical identity + pipeline)

## Delivered

- **Migration `002_lead_mca_identity`:** `debtor_name_normalized`, `mca_tier`, `source_filing_id` (FK to `ucc_filings`, unique), index on normalized name; backfill SQL where applicable.
- **`Lead` ORM** updated; **`get_unprocessed_filings`** uses outer join on `source_filing_id`; **`process_filing`** idempotent per filing, sets normalized name and tier.
- **Export tags** use tier field where applicable.
- **Integration:** `tests/integration/test_mca_pipeline.py` — idempotency and unprocessed batch (Postgres).

## Verification

- `alembic upgrade head` against dev Postgres before relying on new columns.
- `pytest tests/unit -q` — green.
