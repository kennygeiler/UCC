# UCC Lead Generation Platform

Business debt consolidation lead generation from public UCC filings: scrape state SOS data, roll up **consolidation accounts**, detect **MCA funders**, and review everything in a local dashboard.

Architecture constraints and service layout: see `AGENTS.md`. Deeper design notes: [`docs/brief.md`](docs/brief.md), [`docs/brownfield-architecture.md`](docs/brownfield-architecture.md).

## Prerequisites

- **Python 3.12+**
- **PostgreSQL** (local Docker or hosted) for migrations, scrapes, and integration tests

On macOS/Linux with PEP 668, use a virtual environment.

## Quick start

```bash
cd ~/dev/UCC
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Edit DATABASE_URL — example for docker ucc-postgres on port 5433:
# DATABASE_URL=postgresql+asyncpg://user:password@localhost:5433/ucc_pipeline
python -m alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000/dashboard/** for stats, Florida scrape trigger, and the **How this pipeline works** guide.

## Manual Florida scrape workflow

Florida is **manual-only** (no scheduler job). Standard mode paginates `rowNumber` across multiple API index profiles — it does **not** use A–Z text cursors.

1. **Fresh FL data** (idempotent, FL-scoped only):

   ```bash
   python scripts/reset_fl_data.py --dry-run   # preview counts
   python scripts/reset_fl_data.py             # delete FL filings, accounts, leads, runs, checkpoints
   ```

2. **Deep scrape** (defaults in `.env.example`: 50 pages/profile, filing dates, org compact + org actual):

   ```bash
   python scripts/run_fl_scrape.py
   ```

   Post-scrape pipeline runs automatically: classify filings → rollup `business_accounts` → consolidation score → MCA `leads`.

3. **Quick scrape** (tests / CI, ~seconds):

   ```bash
   python scripts/run_fl_scrape.py --quick
   ```

4. **SQL snapshot**:

   ```bash
   python scripts/report_fl_data.py
   ```

Dashboard alternative: **Run Florida scraper** on `/dashboard/` (`POST /dashboard/scrapers/FL/run`, background task).

### Florida env vars

| Variable | Default | Purpose |
|----------|---------|---------|
| `FL_SCRAPE_PAGE_CAP_PER_RUN` | `50` | Pages per index profile per run |
| `FL_SCRAPE_MAX_PAGES` | `500` | Hard cap per profile (with checkpoints) |
| `FL_SCRAPE_INDEX_PROFILES` | org compact + org actual | `Type\|SubOption` pairs, comma-separated |
| `FL_SCRAPE_FETCH_FILING_DATE` | `true` | Fetch `/Filings/{ucc}` for dates |
| `FL_SCRAPE_ENRICH_CONCURRENCY` | `5` | Parallel secured-party / metadata calls |
| `FL_SCRAPE_EXACT_TERMS` | _(empty)_ | Optional Exact-mode MCA lender terms |

Checkpoints in `scraper_checkpoints` resume `rowNumber` per profile between runs.

## Dashboard URLs

| URL | Content |
|-----|---------|
| http://localhost:8000/dashboard/ | Stats, scraper runs, FL run button, pipeline guide |
| http://localhost:8000/dashboard/filings | Raw `ucc_filings` by state |
| http://localhost:8000/dashboard/leads | MCA funder accounts; **Export CSV** for CRM upload |
| http://localhost:8000/dashboard/accounts | Consolidation accounts, tiers, scores |

## Export (CSV)

MCA funder accounts can be exported for CRM import **without API keys** (GoHighLevel and enrichment APIs are out of scope for this pass).

**Dashboard:** On [MCA Leads](http://localhost:8000/dashboard/leads), use **Export CSV**. The download uses the same filters as the table (`state`, `tier` / consolidation tier, `debtor_name`, optional `since_last_run=1`).

**URL:** `GET /dashboard/leads/export.csv?state=FL&tier=priority` — response is UTF-8 CSV with `Content-Disposition: attachment; filename=ucc-mca-leads-FL-YYYY-MM-DD.csv`.

**CLI:**

```bash
python scripts/export_mca_accounts_csv.py --state FL
python scripts/export_mca_accounts_csv.py --state FL --tier priority -o /tmp/mca-priority.csv
```

| Column | Meaning |
|--------|---------|
| `account_id` | `business_accounts.id` |
| `display_name` | Debtor display name |
| `state` | State code |
| `debtor_name_normalized` | Rollup key |
| `consolidation_tier` / `consolidation_score` | Account queue tier and score |
| `mca_funder_count` / `material_ucc_count` | Rollup counts |
| `days_since_last_filing` / `last_event_at` | Recency |
| `mca_funders` | Semicolon-separated MCA secured parties on linked filings |
| `filing_count` / `top_secured_parties` | Filing count; up to 3 distinct secured parties |
| `phone`, `email`, `owner_name`, `estimated_revenue` | Reserved for future enrichment (empty today) |

## Data model (operator view)

| Table | Meaning |
|-------|---------|
| `ucc_filings` | One public UCC row per state + `filing_number` (unique). Upsert on re-scrape. |
| `business_accounts` | Debtor rollup per normalized name + state. `consolidation_score` / `consolidation_tier`. |
| `leads` | Legacy filing-level MCA matches (`detect_mca`); operator **Leads** UI uses `business_accounts` with MCA funders instead. |
| `mca_aliases` | Known MCA lender names — DB is runtime source of truth; seed via `scripts/seed_mca_aliases.py`. |
| `scraper_runs` / `scraper_checkpoints` | Audit log and FL pagination cursors. |

## Understanding the numbers

After a full Florida scrape you may see roughly **2,451 filings**, **~1,946 accounts**, and **~169 MCA lead accounts** (businesses with ≥1 MCA funder on filings), with about **~12 priority** and **~5 work** accounts in the consolidation queue. Filing-level `leads` rows from strict `detect_mca` remain much smaller (~8)—that split is **expected**.

**Deep dive:** [Florida suppress-tier analysis](docs/florida-suppress-tier-analysis.md) — why ~98% of FL accounts are suppress tier, filings vs leads vs accounts, and product fit for debt consolidation vs MCA-stack outreach.

### Filings (`ucc_filings`)

Every UCC row scraped from Florida: banks, SBA lenders, registered agents (for example CSC), insurance companies, MCA funders, and more. One database row per public filing. A **broad index scrape** (paginating the whole FL org index) pulls mostly non-MCA secured parties, so filing count will always be the largest number.

### Leads (MCA funder accounts)

A **lead** = a `business_account` where at least one linked filing has **`lender_class = 'mca_funder'`** (from the consolidation classifier, preferring `mca_aliases.lender_class`) **or** **`is_mca = true`** (strict `detect_mca` pipeline). The dashboard **Leads** page lists these accounts (`mca_funder_count >= 1`), sorted by consolidation score.

Manage lender names at **`/dashboard/mca-lenders`** (`mca_aliases` table). After adding aliases, run **Reclassify FL filings** (or `python scripts/sync_mca_leads.py`) to refresh `lender_class`, account rollup, and lead counts.

**Legacy `leads` table:** Filing-level rows from strict `detect_mca` still exist for enrichment/export experiments but are not the primary operator queue.

**Why MCA lead accounts exceed filing-level leads:** The classifier tags MCA-style secured parties (aliases + keyword heuristics like “capital” / “funding”) more broadly than the strict detector that creates `leads` rows.

### Accounts (`business_accounts`)

One account per **normalized business name + state**, rolled up from all of that debtor’s filings. **`consolidation_score`** (0–100) and **`consolidation_tier`** (`priority`, `work`, `monitor`, `suppress`) are the **primary operator queue** for debt-consolidation outreach.

The account scorer looks at **patterns across all filings** for that business: how many MCA-classified funders appear, how recent activity is, filing velocity, material lender stack, collateral signals when present, and penalties for noise (agents/government) or weak name matches. It can count MCA-related activity from **`lender_class`** (for example `mca_funder`) on filings even when no lead row was created for that filing.

**Why priority/work accounts can exceed leads:** Account tiers use consolidation scoring rules that are **not** the same as the lead table. For example:

- **Two or more MCA funders** on one business can floor the score to **priority** tier (dual-MCA rule), even when individual filings did not all become leads.
- A **recent single-MCA** filing can floor an account to **work** tier.
- The classifier may tag a secured party as `mca_funder` for scoring while the stricter lead detector did not create a lead.

So you might have **~169 MCA lead accounts** but only **~8** filing-level `leads` rows. Use **Leads** for MCA funder businesses; use **Accounts** for the full consolidation tier queue.

### What to work first (operators)

1. **Leads** — MCA funder accounts (`/dashboard/leads`); primary MCA outreach queue.
2. **Accounts** — full consolidation tier sort (`priority` → `work` → `monitor`).
3. **Filings** — raw SOS rows for research and spot-checks.
4. **MCA lenders** — add/edit aliases, then reclassify.

### Reference snapshot (last FL run)

| Metric | Approx. |
|--------|---------|
| FL filings | ~2,451 (100% with `filing_date`) |
| Accounts | ~1,946 |
| Leads | ~8 (strict MCA detector on broad scrape) |
| Tiers | ~12 priority, ~5 work, ~26 monitor, remainder suppress |

In the dashboard, open **How this pipeline works** on `/dashboard/` for the same guide in the UI.

## Scoring

- **consolidation_score** (0–100) on `business_accounts` — debt-consolidation fit from filing patterns (MCA funder count, material UCCs, recency).
- **consolidation_tier** — `priority`, `work`, `monitor`, or `suppress` for outreach ordering.
- **lead_score** on `leads` — MCA secured-party match quality (aliases + fuzzy + heuristics), independent of consolidation.

## Development & testing

```bash
pytest -m "not slow"                    # CI parity
pytest tests/unit/test_reset_fl_data.py tests/unit/test_florida_enrichment.py -v
pytest tests/integration/ -m integration -v   # needs Postgres + DATABASE_URL
```

Integration E2E: `tests/integration/test_fl_reset_scrape_e2e.py` (reset → mocked quick scrape → no duplicate filings).

## Florida API notes

- Base: `https://publicsearchapi.floridaucc.com/search`
- **Standard** search: empty `text`, paginate with `rowNumber` / `nextRowNumber`
- **Exact** search: optional lender terms; no checkpoint persistence
- Enrichment: `/Filings/{ucc}/deb-sec-names`, `/Filings/{ucc}` for filing dates
- **Collateral:** the public `/Filings/{ucc}` payload does not currently expose collateral text; the scraper probes known keys but `collateral_description` usually stays null for FL. MCA collateral heuristics apply when other states populate that field.

After detector changes, refresh MCA without a full rescrape:

```bash
python scripts/refresh_fl_mca.py
python scripts/audit_fl_coverage.py
```

## Migrations

```bash
python -m alembic upgrade head
```

Migration `006` adds `UNIQUE (state, filing_number)` on `ucc_filings` after deduping existing rows.

## Health endpoints

- Pipeline: `GET /health` — `ok` / `degraded`, database connectivity
- Watchdog: separate service; see `AGENTS.md`
